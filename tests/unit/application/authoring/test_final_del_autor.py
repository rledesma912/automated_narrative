"""Spec-690 S1: el final de la autora se lee de un solo lugar (D15) y lo que cambia en
«Preguntas» manda sobre el «¿Cómo termina?» viejo (D14, el bug de §1.1)."""

from src.application.services.authoring import context, workshop_rules
from src.application.services.authoring.outline_narrator import OutlineNarrator
from src.application.services.authoring.planner import OutlinePlanner
from src.domain.models import ActOutline, CriterionStatus, WorkshopItem, WorkshopLevel


def _final(answer: str, status=CriterionStatus.CUMPLE, asked=()) -> WorkshopItem:
    return WorkshopItem(
        criterion="final",
        level=WorkshopLevel.DIRECCION,
        status=status,
        answer=answer,
        asked=list(asked),
        round=1,
    )


def _with(story, *, ending="", item=None):
    direction = story.direction.model_copy(update={"ending": ending})
    return story.model_copy(update={"direction": direction, "workshop": [item] if item else []})


def test_sin_final(story):
    assert context.author_ending(_with(story)) == ""


def test_el_final_viejo_de_tu_idea(story):
    assert context.author_ending(_with(story, ending="Descansa en paz.")) == "Descansa en paz."


def test_preguntas_manda_sobre_el_final_viejo(story):
    s = _with(story, ending="Descansa en paz.", item=_final("Le deja flores y se va."))
    assert context.author_ending(s) == "Le deja flores y se va."


def test_una_pregunta_sin_responder_no_es_un_final(story):
    s = _with(story, item=_final("", CriterionStatus.FALTA))
    assert context.author_ending(s) == ""


def test_el_bug_cambiar_el_final_en_preguntas_llega_al_planificador_y_a_la_voz(story):
    """§1.1: antes, una ronda nueva lo pisaba con `Direction.ending` y el Planificador y la
    Voz seguían leyendo el viejo."""
    s = _with(story, ending="Descansa en paz.", item=_final("Le deja flores y se va."))
    items = workshop_rules.initial_items(s.direction, s.workshop)
    final = next(w for w in items if w.criterion == "final")
    assert final.answer == "Le deja flores y se va."  # la ronda nueva no lo pisa

    prompt = OutlinePlanner(llm=None)._prompt(s)
    assert "Le deja flores y se va." in prompt and "Descansa en paz." not in prompt

    act = ActOutline(number=5, events=["José se despide."])
    assert "Le deja flores y se va." in OutlineNarrator(llm=None)._function(s, act, {})


def test_el_final_viejo_entra_a_preguntas_si_no_hay_otro(story):
    s = _with(story, ending="Descansa en paz.")
    final = next(w for w in workshop_rules.initial_items(s.direction, []) if w.criterion == "final")
    assert (final.status, final.answer) == (CriterionStatus.INTENCIONAL, "Descansa en paz.")


def test_si_pidio_que_se_lo_pregunten_el_final_viejo_no_vuelve(story):
    """D13: con `·final_preguntar`, ni el «¿Cómo termina?» viejo lo resuelve."""
    pedido = _final("", CriterionStatus.FALTA, asked=[workshop_rules.FINAL_PREGUNTAR])
    s = _with(story, ending="Descansa en paz.", item=pedido)
    final = next(
        w for w in workshop_rules.initial_items(s.direction, s.workshop) if w.criterion == "final"
    )
    assert (final.status, final.answer) == (CriterionStatus.FALTA, "")


def test_las_marcas_no_se_leen_como_preguntas():
    item = _final("Se va.", asked=["¿Cómo termina?", workshop_rules.DE_LA_IDEA])
    assert workshop_rules.questions(item) == ["¿Cómo termina?"]
