"""Spec-610 T1.1: partir y unir los actos de un relato guardado."""

import pytest

from src.application.services import narrative_acts
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.domain.models import ActText, Story

ACTO_1 = "Nunca se lo conté a nadie.\n\nEsa noche venía manejando, con el termo entre las piernas."
ACTO_2 = "Levanté el celular.\n\nBajé a mirar el motor, más oscuro que la oscuridad.\n\nSubí."


def _consolidado(*actos: str) -> str:
    story = Story.model_construct(
        beats=[ActText(number=i + 1, generated_act=texto) for i, texto in enumerate(actos)]
    )
    return GenerateNarrativesUseCase._consolidate_content(story)


def test_ida_y_vuelta_identica_con_la_consolidacion():
    content = _consolidado(ACTO_1, ACTO_2)
    assert narrative_acts.join(narrative_acts.split(content)) == content


def test_ida_y_vuelta_con_preambulo():
    content = "# Título\n\nUna nota.\n\n" + _consolidado(ACTO_1, ACTO_2)
    partido = narrative_acts.split(content)
    assert partido.preamble == "# Título\n\nUna nota."
    assert narrative_acts.join(partido) == content


def test_actos_y_parrafos():
    partido = narrative_acts.split(_consolidado(ACTO_1, ACTO_2))
    assert partido.numbers() == [1, 2]
    assert partido.paragraphs(2) == [
        "Levanté el celular.",
        "Bajé a mirar el motor, más oscuro que la oscuridad.",
        "Subí.",
    ]


def test_sin_actos_todo_es_preambulo():
    partido = narrative_acts.split("Un texto suelto.\n\nOtro párrafo.")
    assert partido.acts == {}
    assert partido.preamble == "Un texto suelto.\n\nOtro párrafo."


def test_reemplazar_un_acto_no_toca_los_demas():
    content = _consolidado(ACTO_1, ACTO_2)
    nuevo = narrative_acts.replace_act(content, 2, "Otro texto.\n\nY otro párrafo.")
    partido = narrative_acts.split(nuevo)
    assert partido.acts[1] == ACTO_1
    assert partido.acts[2] == "Otro texto.\n\nY otro párrafo."


def test_reemplazar_normaliza_el_texto():
    content = _consolidado(ACTO_1, ACTO_2)
    sucio = "  Primero.  \r\n\r\n\r\n\n   \nSegundo.\r\n"
    partido = narrative_acts.split(narrative_acts.replace_act(content, 1, sucio))
    assert partido.acts[1] == "Primero.\n\nSegundo."


def test_reemplazar_un_acto_que_no_existe():
    with pytest.raises(KeyError):
        narrative_acts.replace_act(_consolidado(ACTO_1), 3, "Texto.")


def test_un_parrafo_con_salto_simple_sigue_siendo_uno():
    assert narrative_acts.paragraphs("Una línea\nque sigue.\n\nOtro.") == [
        "Una línea\nque sigue.",
        "Otro.",
    ]
