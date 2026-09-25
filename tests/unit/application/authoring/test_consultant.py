from src.application.services.authoring import workshop_rules as wr
from src.application.services.authoring.consultant import WorkshopConsultant
from src.domain.models import CriterionStatus as S
from src.domain.models import WorkshopItem
from tests.unit.application.authoring.conftest import ScriptedLLM


def _eval(criterio, estado, pregunta="", opciones=()):
    return {
        "criterio": criterio,
        "estado": estado,
        "pregunta": pregunta,
        "opciones": list(opciones),
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
    assert enum == ["meta", "en_juego", "vulnerabilidad", "historia_secreta"]
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
    assert "[meta] Qué quiere. Pregunta: «¿Qué quiere?» → Respuesta: Llegar a casa" in prompt
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
    assert llm.calls == [] and r.finish.kind == "cumple"
