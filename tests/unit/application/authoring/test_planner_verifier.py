import pytest

from src.application.services.authoring import workshop_rules as wr
from src.application.services.authoring.planner import OutlinePlanner
from src.application.services.authoring.verifier import OutlineVerifier, rule_warnings
from src.domain.exceptions import LLMStructuredOutputError
from src.domain.models import ActOutline, Entity, OutlineWarning
from tests.unit.application.authoring.conftest import ScriptedLLM


def _acto(n, **kw):
    base = {
        "numero": n,
        "como_llega": "" if n == 1 else "Esa noche sigue",
        "objetivo": f"quiere {n}",
        "hechos": [f"hecho {n}"],
        "cambio_de": "a",
        "cambio_a": "b",
        "escenario": "La ruta",
        "en_escena": ["José"],
        "se_guarda": "",
        "se_revela_en": 0,
        "siembra": [],
        "retoma": [],
        "decisiones": [],
    }
    return {**base, **kw}


def _with_decisions(story):
    items = wr.initial_items(story.direction, [])
    items = [wr.answer(w, "Llegar a casa") if w.criterion == "meta" else w for w in items]
    return story.model_copy(update={"workshop": items})


async def test_planifica_cinco_actos(story):
    story = _with_decisions(story)
    llm = ScriptedLLM(
        {"actos": [_acto(n, decisiones=["meta", "inventada"]) for n in (5, 4, 3, 2, 1)]}
    )

    acts, _ = await OutlinePlanner(llm).plan(story)

    assert [a.number for a in acts] == [1, 2, 3, 4, 5]
    assert acts[0].decisions == ["meta"]  # las inventadas se descartan
    assert acts[0].goal == "quiere 1" and acts[0].events == ["hecho 1"]
    prompt = llm.calls[0]["prompt"]
    assert "[meta] Qué quiere José (va en el acto 1): Llegar a casa" in prompt
    assert (
        "5. Desenlace (intensidad baja): cerrar la historia con el final que decidió el autor"
        in prompt
    )


async def test_sin_cinco_actos_reintenta_y_falla(story):
    bad = {"actos": [_acto(n) for n in (1, 2, 3, 4)]}
    llm = ScriptedLLM(bad, bad)
    with pytest.raises(LLMStructuredOutputError, match="actos 1 a 5"):
        await OutlinePlanner(llm).plan(story)
    assert len(llm.calls) == 2


def test_reglas_sin_llm(story):
    story = story.model_copy(
        update={
            "entities": [
                Entity(story_id=story.id, order_index=0, name="La mujer", nature_id="fantasma")
            ]
        }
    )
    outline = [
        ActOutline(
            number=1,
            events=["x"],
            change_from="Tranquilo",
            change_to="tranquilo.",
            on_stage=["José", "El sereno", "La mujer (espectro)"],
            seeds=["El ramo"],
        ),
        ActOutline(number=2, events=[], payoffs=[]),
    ]
    warnings = rule_warnings(story, outline)
    text = " ".join(w.text for w in warnings[1])
    assert "termina igual que empieza" in text
    assert "«El sereno» aparece en este acto" in text
    assert "La mujer" not in text  # la amenaza no es elenco
    assert "«El ramo» aparece acá" in text
    assert "no pasa nada todavía" in " ".join(w.text for w in warnings[2])
    assert {w.key for w in warnings[1]} >= {"sin_cambio", "elenco:el sereno", "siembra:el ramo"}


async def test_verificador_saca_decisiones_que_faltan_y_limita_avisos(story):
    story = _with_decisions(story)
    outline = [
        ActOutline(
            number=n,
            bridge="Esa noche sigue",
            events=["x"],
            change_from="a",
            change_to="b",
            decisions=["meta"] if n == 1 else [],
        )
        for n in range(1, 6)
    ]
    llm = ScriptedLLM(
        {
            "decisiones": [{"decision": "meta", "acto": 0}, {"decision": "inventada", "acto": 2}],
            "avisos": [{"acto": 2, "aviso": f"aviso {i}"} for i in range(4)]
            + [{"acto": 9, "aviso": "x"}],
        }
    )

    v = await OutlineVerifier(llm).verify(story, outline)

    assert v.missing_decisions == ["meta"]  # el final intencional va siempre al último acto
    assert v.outline[0].decisions == []
    assert v.outline[4].decisions == ["final"]
    assert [w.text for w in v.outline[1].warnings] == ["aviso 0", "aviso 1"]


async def test_el_final_intencional_va_al_ultimo_acto(story):
    story = _with_decisions(story)
    llm = ScriptedLLM({"actos": [_acto(n) for n in range(1, 6)]})
    acts, _ = await OutlinePlanner(llm).plan(story)
    assert acts[-1].decisions == ["final"]
    assert all("final" not in a.decisions for a in acts[:-1])


async def test_el_verificador_no_saca_el_final_intencional(story):
    story = _with_decisions(story)
    outline = [
        ActOutline(
            number=n,
            bridge="Esa noche sigue",
            events=["x"],
            change_from="a",
            change_to="b",
            decisions=["final"] if n == 5 else [],
        )
        for n in range(1, 6)
    ]
    llm = ScriptedLLM({"decisiones": [{"decision": "final", "acto": 0}], "avisos": []})
    v = await OutlineVerifier(llm).verify(story, outline)
    assert v.outline[4].decisions == ["final"] and "final" not in v.missing_decisions


def test_hilos_sueltos_en_un_solo_aviso(story):
    outline = [
        ActOutline(number=1, events=["x"], seeds=["La música", "El vestido"]),
        ActOutline(number=2, events=["y"], payoffs=[]),
    ]
    (warning,) = rule_warnings(story, outline)[1]
    assert (
        warning.text
        == "«La música», «El vestido» aparecen acá y no vuelven en ningún acto posterior: ¿los retomamos?"
    )
    assert warning.key == "siembra:la musica|siembra:el vestido"


async def test_como_maximo_tres_avisos_por_acto(story):
    outline = [
        ActOutline(
            number=1, events=[], change_from="a", change_to="a", on_stage=["X", "Y"], seeds=["s"]
        )
    ]
    llm = ScriptedLLM({"decisiones": [], "avisos": [{"acto": 1, "aviso": "del LLM"}]})
    v = await OutlineVerifier(llm).verify(story, outline)
    assert len(v.outline[0].warnings) == 3
    assert "del LLM" not in [w.text for w in v.outline[0].warnings]  # primero las reglas


async def test_escenarios_sin_agregados_y_secreto_en_el_acto_4(story):
    items = wr.initial_items(story.direction, [])
    items = [
        wr.answer(w, "No paró aquella noche") if w.criterion == "historia_secreta" else w
        for w in items
    ]
    story = story.model_copy(update={"workshop": items})
    llm = ScriptedLLM(
        {
            "actos": [
                _acto(n, escenario="Ruta 36 (regreso)" if n == 2 else "Ruta 36")
                for n in range(1, 6)
            ]
        }
    )
    acts, _ = await OutlinePlanner(llm).plan(story)
    assert {a.scenario for a in acts} == {"Ruta 36"}
    assert (
        "4. Acción descendente (intensidad media-alta): llevar al protagonista al colapso y reaccion; acá el protagonista descubre o confiesa la historia secreta"
        in llm.calls[0]["prompt"]
    )


async def test_la_revision_ubica_decisiones_que_el_planificador_no_etiqueto(story):
    story = _with_decisions(story)
    outline = [
        ActOutline(number=n, events=["x"], change_from="a", change_to="b") for n in range(1, 6)
    ]
    llm = ScriptedLLM({"decisiones": [{"decision": "meta", "acto": 3}], "avisos": []})
    v = await OutlineVerifier(llm).verify(story, outline)
    assert v.outline[2].decisions == ["meta"]
    assert v.outline[4].decisions == ["final"]
    assert v.missing_decisions == []


# ── Spec-550 H10: lo ignorado no vuelve ─────────────────────────────────────


def test_una_siembra_ignorada_no_vuelve_y_el_aviso_se_arma_sin_ella(story):
    outline = [
        ActOutline(
            number=1,
            events=["x"],
            seeds=["La música", "El vestido"],
            warnings=[
                OutlineWarning(
                    text="«La música» …", key="siembra:la musica", source="regla", dismissed=True
                )
            ],
        ),
        ActOutline(number=2, events=["y"]),
    ]
    (warning,) = rule_warnings(story, outline, {1: outline[0].dismissed_keys()})[1]
    assert (
        warning.text
        == "«El vestido» aparece acá y no vuelve en ningún acto posterior: ¿lo retomamos?"
    )


async def test_un_aviso_de_la_ia_ignorado_llega_al_prompt_y_se_filtra(story):
    ignorado = OutlineWarning.from_ai("El micro aparece de golpe en el acto 2.")
    outline = [
        ActOutline(
            number=n,
            bridge="Esa noche sigue",
            events=["x"],
            change_from="a",
            change_to="b",
            warnings=[ignorado.model_copy(update={"dismissed": True})] if n == 2 else [],
        )
        for n in range(1, 6)
    ]
    llm = ScriptedLLM(
        {
            "decisiones": [],
            "avisos": [{"acto": 2, "aviso": "El micro aparece de golpe en el acto 2"}],
        }
    )
    v = await OutlineVerifier(llm).verify(story, outline)

    assert "El micro aparece de golpe en el acto 2." in llm.calls[0]["prompt"]
    assert [w.dismissed for w in v.outline[1].warnings] == [True]  # no se duplicó


# ── Spec-560 A1 + A3: puente entre actos y continuidad ──────────────────────


async def test_el_planificador_trae_como_llega_salvo_en_el_acto_1(story):
    llm = ScriptedLLM({"actos": [_acto(n, como_llega=f"puente {n}") for n in range(1, 6)]})
    acts, _ = await OutlinePlanner(llm).plan(story)
    assert [a.bridge for a in acts] == ["", "puente 2", "puente 3", "puente 4", "puente 5"]


def test_regla_sin_puente_en_los_actos_2_a_5(story):
    outline = [
        ActOutline(number=n, events=["x"], bridge="" if n in (1, 3) else "sigue")
        for n in range(1, 4)
    ]
    warnings = rule_warnings(story, outline)
    assert [w.key for w in warnings.get(3, [])] == ["sin_puente"]
    assert 1 not in warnings and 2 not in warnings  # el acto 1 no necesita puente


# ── Spec-560 A4: lo que todavía no se cuenta y dónde se revela ──────────────


async def test_el_planificador_trae_el_acto_que_revela_solo_si_es_posterior(story):
    actos = [
        _acto(n, se_guarda="Quién es ella", se_revela_en=r)
        for n, r in ((1, 4), (2, 1), (3, 0), (4, 5), (5, 0))
    ]
    acts, _ = await OutlinePlanner(ScriptedLLM({"actos": actos})).plan(story)
    assert [a.reveal_act for a in acts] == [4, 0, 0, 5, 0]


def test_regla_lo_guardado_sin_acto_que_lo_revele(story):
    outline = [
        ActOutline(number=1, events=["x"], held_back="Quién es ella", reveal_act=3),
        ActOutline(number=2, bridge="sigue", events=["x"], held_back="El accidente"),
    ]
    warnings = rule_warnings(story, outline)
    assert 1 not in warnings
    assert [w.key for w in warnings[2]] == ["sin_revelacion"]


# ── Spec-560 A6: al rearmar, el Planificador recibe los avisos visibles ─────


async def test_al_rearmar_recibe_los_avisos_visibles_y_no_los_ignorados(story):
    story = story.model_copy(
        update={
            "outline": [
                ActOutline(
                    number=2,
                    events=["x"],
                    warnings=[
                        OutlineWarning.from_ai("El encuentro repite el del acto 1."),
                        OutlineWarning.from_ai("Aviso ignorado.").model_copy(
                            update={"dismissed": True}
                        ),
                    ],
                )
            ]
        }
    )
    llm = ScriptedLLM({"actos": [_acto(n) for n in range(1, 6)]})
    await OutlinePlanner(llm).plan(story)
    prompt = llm.calls[0]["prompt"]
    assert "PROBLEMAS QUE MARCÓ LA REVISIÓN" in prompt
    assert "- Acto 2: El encuentro repite el del acto 1." in prompt
    assert "Aviso ignorado." not in prompt


# ── Spec-560 A5: el efecto pesa en la escaleta ──────────────────────────────


def _with_effect(story, effect, other=""):
    direction = story.direction.model_copy(update={"effect": effect, "effect_other": other})
    return story.model_copy(update={"direction": direction})


async def test_el_planificador_recibe_la_receta_del_efecto(story):
    llm = ScriptedLLM({"actos": [_acto(n) for n in range(1, 6)]})
    await OutlinePlanner(llm).plan(_with_effect(story, "susto"))
    prompt = llm.calls[0]["prompt"]
    assert "CÓMO TIENE QUE PEGAR (el efecto que busca el autor: Susto)" in prompt
    assert "dos irrupciones bruscas" in prompt


async def test_otro_usa_el_texto_del_autor(story):
    llm = ScriptedLLM({"actos": [_acto(n) for n in range(1, 6)]})
    await OutlinePlanner(llm).plan(_with_effect(story, "otro", "Que dé asco más que miedo"))
    assert "Que dé asco más que miedo" in llm.calls[0]["prompt"]


async def test_el_verificador_controla_la_receta(story):
    outline = [ActOutline(number=n, bridge="sigue", events=["x"]) for n in range(1, 6)]
    llm = ScriptedLLM({"decisiones": [], "avisos": []})
    await OutlineVerifier(llm).verify(_with_effect(story, "revelacion"), outline)
    prompt = llm.calls[0]["prompt"]
    assert "EFECTO QUE BUSCA EL AUTOR: Horror que se revela" in prompt
    assert "se revela en el acto 4" in prompt


def test_sin_efecto_no_hay_receta(story):
    from src.application.services.authoring import context
    from src.application.services.template_loader import TemplateLoader

    assert context.effect_block(_with_effect(story, ""), TemplateLoader()) == ""


# ── Spec-630 B11: lo que se edita en «Los actos» llega a la IA ───────────────


def test_el_verificador_ve_quienes_estan_como_cambia_y_las_reglas_del_acto(story):
    from src.domain.models import TypedRule

    acts = [
        ActOutline(
            number=1,
            events=["Arranca"],
            on_stage=["José", "Marta"],
            change_from="tranquilo",
            change_to="asustado",
        ),
        ActOutline(number=2, events=["Frena"]),
    ]
    story.typed_rules = [
        TypedRule(id="R1", story_id=story.id, content="Solo de noche", applies_to_beat=1),
        TypedRule(id="R2", story_id=story.id, content="Regla global", applies_to_beat=None),
    ]
    prompt = OutlineVerifier(llm=None)._prompt(story, acts)
    acto1, acto2 = prompt.split("ACTO 1")[1].split("ACTO 2")
    assert "En escena: José, Marta" in acto1
    assert "Cómo cambia: tranquilo → asustado" in acto1
    assert "Reglas de este acto: Solo de noche" in acto1
    # Sin datos, sin líneas; y la regla global no es de ningún acto.
    for line in ("En escena:", "Cómo cambia:", "Reglas de este acto:"):
        assert line not in acto2.split("AVISOS QUE EL AUTOR")[0]
    assert "Regla global" not in prompt


def test_el_planificador_respeta_las_reglas_de_cada_acto(story):
    from src.domain.models import TypedRule

    assert "REGLAS QUE PUSO EL AUTOR" not in OutlinePlanner(llm=None)._prompt(story)
    story.typed_rules = [
        TypedRule(id="R1", story_id=story.id, content="Aparece en el espejo", applies_to_beat=3),
        TypedRule(id="R2", story_id=story.id, content="Solo de noche", applies_to_beat=1),
    ]
    prompt = OutlinePlanner(llm=None)._prompt(story)
    i = prompt.index("REGLAS QUE PUSO EL AUTOR")
    assert prompt.index("- Acto 1: Solo de noche", i) < prompt.index(
        "- Acto 3: Aparece en el espejo", i
    )


# ── Spec-650: el relato corto tiene un tope de hechos por acto ────────────────


def test_corto_con_muchos_hechos_avisa_y_el_largo_no(story):
    outline = [
        ActOutline(number=1, events=["a", "b", "c", "d"], bridge=""),
        ActOutline(number=2, events=["a"] * 5, bridge="Después."),
        ActOutline(number=3, events=["a", "b", "c", "d"], bridge="Después."),
    ]
    corto = rule_warnings(story.model_copy(update={"structure": "corto"}), outline)
    keys = {n: {w.key for w in ws} for n, ws in corto.items()}
    assert "muchos_hechos" in keys[1] and "muchos_hechos" in keys[3]
    assert "muchos_hechos" not in keys.get(2, set())  # 5 entra en el nudo
    texto = next(w.text for w in corto[3] if w.key == "muchos_hechos")
    assert "tiene 4 hechos" in texto and "entran 3" in texto

    largo = rule_warnings(story, outline)
    assert not any(w.key == "muchos_hechos" for ws in largo.values() for w in ws)


def test_muchos_hechos_ignorado_no_vuelve(story):
    outline = [ActOutline(number=3, events=["a", "b", "c", "d"], bridge="Después.")]
    corto = story.model_copy(update={"structure": "corto"})
    assert not rule_warnings(corto, outline, {3: {"muchos_hechos"}}).get(3)
