from src.application.services.authoring import workshop_rules as wr
from src.application.services.authoring.consultant import WorkshopConsultant
from src.domain.models import CriterionStatus as S
from src.domain.models import WorkshopItem
from tests.unit.application.authoring.conftest import ScriptedLLM


def _eval(criterio, estado, pregunta="", opciones=(), motivo=""):
    return {
        "criterio": criterio,
        "estado": estado,
        "pregunta": pregunta,
        "opciones": list(opciones),
        "motivo": motivo,
    }


async def test_primera_ronda_evalua_todo_menos_el_final_intencional(story):
    llm = ScriptedLLM(
        {
            "evaluaciones": [
                _eval("meta", "falta", "¿Qué quiere José?", ["a", "b"]),
                _eval("en_juego", "cumple"),
            ]
        }
    )
    r = await WorkshopConsultant(llm).analyze(story)

    schema = llm.calls[0]["response_schema"]
    enum = schema["$defs"]["EvaluacionCriterio"]["properties"]["criterio"]["enum"]
    assert enum == [
        "meta",
        "inquietud",
        "en_juego",
        "vulnerabilidad",
        "transgresion",
        "historia_secreta",
        "descubrimiento",
        "reaccion",
    ]
    items = {w.criterion: w for w in r.items}
    assert items["meta"].question == "¿Qué quiere José?" and items["meta"].round == 1
    assert items["en_juego"].status == S.CUMPLE
    assert items["final"].status == S.INTENCIONAL
    assert r.finish.kind == "abierto"
    prompt = llm.calls[0]["prompt"]
    assert "Efecto que busca el autor: Pavor creciente" in prompt
    assert "Cómo termina: Descansa en paz. (DECIDIDO POR EL AUTOR" in prompt
    assert "Hamartia" not in prompt  # la teoría no va al prompt


async def test_la_segunda_ronda_recibe_pregunta_y_respuesta_y_lo_pendiente(story):
    items = wr.initial_items(story.direction, [])
    by = {w.criterion: w for w in items}
    by["meta"] = wr.answer(
        WorkshopItem(criterion="meta", question="¿Qué quiere?", round=1), "Llegar a casa"
    )
    by["en_juego"] = WorkshopItem(
        criterion="en_juego", status=S.FALTA, question="¿Qué pierde?", round=1
    )
    story = story.model_copy(update={"workshop": list(by.values())})
    llm = ScriptedLLM({"evaluaciones": [_eval("en_juego", "parcial", "otra forma de preguntar")]})

    r = await WorkshopConsultant(llm).analyze(story)

    prompt = llm.calls[0]["prompt"]
    assert (
        "[meta] Qué quiere José (va en el acto 1). Pregunta: «¿Qué quiere?» → Respuesta: Llegar a casa"
        in prompt
    )
    assert "- [en_juego] «¿Qué pierde?»" in prompt
    enum = llm.calls[0]["response_schema"]["$defs"]["EvaluacionCriterio"]["properties"]["criterio"][
        "enum"
    ]
    assert "meta" not in enum
    en_juego = next(w for w in r.items if w.criterion == "en_juego")
    assert (en_juego.question, en_juego.status, en_juego.round) == ("¿Qué pierde?", S.PARCIAL, 2)
    assert r.finish.kind == "no_suma"


async def test_sin_pendientes_no_llama_a_la_ia(story):
    items = [
        wr.answer(w, "x") if w.status != S.INTENCIONAL else w
        for w in wr.initial_items(story.direction, [])
    ]
    llm = ScriptedLLM()
    r = await WorkshopConsultant(llm).analyze(story.model_copy(update={"workshop": items}))
    assert llm.calls == [] and r.finish.kind == "respondido"
    assert "no le queda nada para preguntarte" in r.finish.text


# ── Spec-670 D8 / D12: «No va en tu historia» ─────────────────────────────────


def _con_forma(story, forma):
    return story.model_copy(
        update={"direction": story.direction.model_copy(update={"form": forma})}
    )


async def test_no_va_queda_con_su_motivo_y_no_se_vuelve_a_evaluar(story):
    llm = ScriptedLLM(
        {
            "evaluaciones": [
                _eval(
                    "transgresion",
                    "no_aplica",
                    "¿Qué hizo José?",
                    ["algo"],
                    motivo="Nadie provoca al fantasma.",
                ),
            ]
        }
    )
    r = await WorkshopConsultant(llm).analyze(story)
    item = next(w for w in r.items if w.criterion == "transgresion")
    assert (item.status, item.question, item.options) == (
        S.NO_APLICA,
        "Nadie provoca al fantasma.",
        [],
    )
    assert "transgresion" not in {w.criterion for w in wr.to_evaluate(r.items)}


async def test_preguntarmelo_igual_impide_otro_no_va(story):
    """D12: reabierto por el autor, la IA ya no lo puede descartar: queda como pregunta."""
    item = WorkshopItem(criterion="transgresion", status=S.NO_APLICA, question="No va.")
    reabierto = wr.reopen(item)
    assert (reabierto.status, reabierto.question) == (S.FALTA, "")
    assert wr.no_aplica_rejected(reabierto)

    llm = ScriptedLLM(
        {
            "evaluaciones": [
                _eval(
                    "transgresion",
                    "no_aplica",
                    "¿Qué hace José con el espejo?",
                    ["Lo mira"],
                    motivo="Otra vez",
                )
            ]
        }
    )
    r = await WorkshopConsultant(llm).analyze(story.model_copy(update={"workshop": [reabierto]}))
    item = next(w for w in r.items if w.criterion == "transgresion")
    assert (item.status, item.question) == (S.FALTA, "¿Qué hace José con el espejo?")
    assert "pidió que se lo pregunten" in llm.calls[0]["prompt"]


async def test_dos_de_la_forma_que_no_van_avisan_que_la_forma_esta_mal_elegida(story):
    llm = ScriptedLLM(
        {
            "evaluaciones": [
                _eval("transgresion", "no_aplica", motivo="Nadie la provoca."),
                _eval("historia_secreta", "no_aplica", motivo="No hay nada de José."),
            ]
        }
    )
    r = await WorkshopConsultant(llm).analyze(story)
    assert r.finish.kind == "mal_elegida"
    assert "2 de sus preguntas no van" in r.finish.text


def test_lo_que_no_va_llega_a_la_ia_con_su_motivo(story):
    from src.application.services.authoring import context
    from src.application.services.template_loader import TemplateLoader

    s = story.model_copy(
        update={
            "workshop": [
                WorkshopItem(
                    criterion="transgresion", status=S.NO_APLICA, question="Nadie lo provoca."
                )
            ]
        }
    )
    texto = context.decisions_block(s, TemplateLoader())
    assert "LO QUE NO VA EN ESTA HISTORIA" in texto
    assert "- [transgresion] Lo que José no tendría que haber hecho: Nadie lo provoca." in texto
