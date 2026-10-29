"""Spec-700 A3/A4: con la idea cambiada, la IA marca lo que ya no coincide, sin pisarlo."""

from src.application.services.authoring import revisor
from src.application.services.authoring import workshop_rules as wr
from src.domain.models import CriterionStatus, WorkshopItem
from tests.unit.application.authoring.conftest import ScriptedLLM


def _taller(story):
    items = [
        WorkshopItem(criterion="meta", status=CriterionStatus.CUMPLE, answer="Volver a casa."),
        WorkshopItem(
            criterion="reaccion", status=CriterionStatus.CUMPLE, answer="Se va del pueblo."
        ),
        WorkshopItem(criterion="transgresion", status=CriterionStatus.INTENCIONAL, answer="Mira."),
        WorkshopItem(criterion="inquietud", status=CriterionStatus.FALTA, question="¿Qué nota?"),
        WorkshopItem(
            criterion="final", status=CriterionStatus.INTENCIONAL, answer="Descansa en paz."
        ),
    ]
    return story.model_copy(update={"workshop": items})


def test_a_revisar_respuestas_y_el_final_que_no_salio_de_la_idea(story):
    story = _taller(story)
    assert [w.criterion for w in revisor.a_revisar(story)] == ["meta", "reaccion", "final"]
    final = next(w for w in story.workshop if w.criterion == "final")
    final.asked = [wr.DE_LA_IDEA]  # lo vuelve a sacar la 690
    assert [w.criterion for w in revisor.a_revisar(story)] == ["meta", "reaccion"]


async def test_marca_sin_pisar_y_desmarca_lo_que_ahora_coincide(story):
    story = _taller(story)
    story.workshop[0] = wr.mark_no_coincide(story.workshop[0], "Algo viejo.")
    llm = ScriptedLLM(
        {
            "revisiones": [
                {"criterio": "meta", "coincide": True, "motivo": ""},
                {"criterio": "reaccion", "coincide": False, "motivo": "Ahora  se queda."},
                {"criterio": "final", "coincide": False, "motivo": ""},  # sin motivo: no marca
            ]
        }
    )

    changed = await revisor.RevisorDeRespuestas(llm).revisar(story)

    by_id = {w.criterion: w for w in changed}
    assert set(by_id) == {"meta", "reaccion"}
    assert wr.no_coincide(by_id["meta"]) == ""
    assert by_id["reaccion"].answer == "Se va del pueblo."  # la respuesta no se toca
    assert wr.no_coincide(by_id["reaccion"]) == "Ahora se queda."
    assert "LA IDEA NUEVA:" in llm.calls[0]["prompt"]
    assert "[transgresion]" not in llm.calls[0]["prompt"]  # «a propósito» no se revisa


async def test_sin_respuestas_no_llama_a_la_ia(story):
    llm = ScriptedLLM()
    assert await revisor.RevisorDeRespuestas(llm).revisar(story) == []
    assert llm.calls == []


def test_tocar_la_respuesta_saca_la_marca():
    item = wr.mark_no_coincide(
        WorkshopItem(criterion="meta", status=CriterionStatus.CUMPLE, answer="A", asked=["¿Q?"]),
        "Ya no va.",
    )
    assert wr.no_coincide(item) == "Ya no va." and wr.questions(item) == ["¿Q?"]
    for after in (
        wr.answer(item, "B"),
        wr.mark_intentional(item, "B"),
        wr.reopen(item),
        wr.keep(item),
    ):
        assert wr.no_coincide(after) == ""
    assert wr.keep(item).answer == "A"
    # Marcar de nuevo reemplaza el motivo (una sola marca).
    again = wr.mark_no_coincide(item, "Otro motivo.")
    assert [a for a in again.asked if a.startswith(wr.NO_COINCIDE)] == ["·no_coincide:Otro motivo."]
