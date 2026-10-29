"""Spec-700 D12–D14: la idea que leyó la IA y qué cambió."""

from src.application.services.authoring import context
from src.domain.models import ActOutline


def test_retocar_signos_mayusculas_y_espacios_no_es_cambiar_la_idea(story):
    story = context.con_idea_leida(story, "preguntas")
    assert story.direction.idea_preguntas == story.direction.premise
    story.direction.premise = "  JOSÉ ve por el espejo, a una mujer… que murió en su micro "
    assert context.idea_cambio(story)["preguntas"] is False
    story.direction.premise = "José ve por el espejo a un hombre que murió en su micro."
    assert context.idea_cambio(story)["preguntas"] is True


def test_sin_de_que_trata_la_idea_es_la_sinopsis(story):
    story.direction.premise = ""
    assert context.idea(story) == story.sinopsis


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


def test_lo_que_cambio_por_oracion():
    antes = "José maneja. Ve a una mujer. Se asusta.\nLlega a la terminal."
    ahora = "José maneja. Ve a un hombre. Se asusta.\nLlega a la terminal. Renuncia."
    assert context.lo_que_cambio(antes, ahora) == (
        ["Ve a una mujer."],
        ["Ve a un hombre.", "Renuncia."],
    )
    assert context.lo_que_cambio("", "Una idea.") == ([], ["Una idea."])
