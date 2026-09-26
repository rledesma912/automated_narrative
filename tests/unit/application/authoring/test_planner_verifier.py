import pytest

from src.application.services.authoring import workshop_rules as wr
from src.application.services.authoring.planner import OutlinePlanner
from src.application.services.authoring.verifier import OutlineVerifier, rule_warnings
from src.domain.exceptions import LLMStructuredOutputError
from src.domain.models import ActOutline, Entity
from tests.unit.application.authoring.conftest import ScriptedLLM


def _acto(n, **kw):
    base = {
        "numero": n,
        "objetivo": f"quiere {n}",
        "hechos": [f"hecho {n}"],
        "cambio_de": "a",
        "cambio_a": "b",
        "escenario": "La ruta",
        "en_escena": ["José"],
        "se_guarda": "",
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
    assert "[meta] Qué quiere: Llegar a casa" in prompt
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
    text = " ".join(warnings[1])
    assert "termina igual que empieza" in text
    assert "«El sereno» está en escena" in text
    assert "La mujer" not in text  # la amenaza no es elenco
    assert "«El ramo» se siembra" in text
    assert "no tiene hechos" in " ".join(warnings[2])


async def test_verificador_saca_decisiones_que_faltan_y_limita_avisos(story):
    story = _with_decisions(story)
    outline = [
        ActOutline(
            number=n,
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
    assert v.outline[1].warnings == ["aviso 0", "aviso 1"]


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
        warning == "«La música», «El vestido» se siembran acá y ningún acto posterior los retoma."
    )


async def test_como_maximo_tres_avisos_por_acto(story):
    outline = [
        ActOutline(
            number=1, events=[], change_from="a", change_to="a", on_stage=["X", "Y"], seeds=["s"]
        )
    ]
    llm = ScriptedLLM({"decisiones": [], "avisos": [{"acto": 1, "aviso": "del LLM"}]})
    v = await OutlineVerifier(llm).verify(story, outline)
    assert len(v.outline[0].warnings) == 3
    assert "del LLM" not in v.outline[0].warnings  # primero las reglas


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
