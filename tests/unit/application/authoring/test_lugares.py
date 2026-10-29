"""Spec-710 D10: los lugares de los hechos pasan a ser lugares de la historia."""

from src.application.services.authoring import lugares
from src.domain.models import ActOutline, Scenario


def test_nuevos_en_orden_sin_repetir_ni_los_que_ya_estan(story):
    story.scenarios = [Scenario(story_id=story.id, order_index=0, name="La ruta")]
    acts = [
        ActOutline(number=2, events=["a", "b"], event_places=["La garita", "la ruta"]),
        ActOutline(number=1, events=["a"], event_places=["La terminal (de noche)"]),
        ActOutline(number=3, events=["a"], scenario="La garita"),  # viejo: su escenario
    ]
    assert lugares.nuevos(story, acts) == ["La terminal (de noche)", "La garita"]

    out = lugares.con_lugares(story, ["La garita"])
    assert [(s.name, s.order_index) for s in out.scenarios] == [("La ruta", 0), ("La garita", 1)]
    assert lugares.con_lugares(story, []) is story
