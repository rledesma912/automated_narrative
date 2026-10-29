"""Spec-700 D12–D14: el sello de la idea que leyó la IA."""

from src.application.services.authoring import context
from src.domain.models import ActOutline


def test_el_hash_ignora_signos_mayusculas_y_espacios(story):
    a = context.idea_hash(story)
    story.direction.premise = "  JOSÉ ve por el espejo, a una mujer… que murió en su micro "
    assert context.idea_hash(story) == a and len(a) == 12
    story.direction.premise = "José ve por el espejo a un hombre que murió en su micro."
    assert context.idea_hash(story) != a


def test_sin_de_que_trata_usa_la_sinopsis_y_sin_nada_no_hay_hash(story):
    story.direction.premise = ""
    assert context.idea_hash(story) != ""
    story.sinopsis = ""
    assert context.idea_hash(story) == ""


def test_sin_sello_no_se_sabe_y_los_actos_solo_con_actos(story):
    assert context.idea_cambio(story) == {"preguntas": False, "actos": False}
    story = context.con_idea_leida(context.con_idea_leida(story, "preguntas"), "actos")
    story.direction.premise += " Y se va."
    assert context.idea_cambio(story) == {"preguntas": True, "actos": False}
    story.outline = [ActOutline(number=1)]
    assert context.idea_cambio(story) == {"preguntas": True, "actos": True}


def test_sin_direccion_no_se_inventa_una(story):
    story.direction = None
    assert context.con_idea_leida(story, "actos").direction is None
    assert context.idea_cambio(story) == {"preguntas": False, "actos": False}
