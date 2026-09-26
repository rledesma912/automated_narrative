"""Spec-470 S1: guía de oficio, parentescos y primera persona en la Voz."""

import pytest

from src.application.services import PromptBuilder
from src.domain.models import Story

CAST = [
    {"id": "P1", "name": "Irene", "role": "Narradora y protagonista; nuera de María"},
    {"id": "P2", "name": "Ricardo", "role": "Esposo de Irene; hijo de María"},
    {"id": "P5", "name": "María", "role": "Suegra de Irene; madre de Ricardo"},
]


def _story(**config) -> Story:
    return Story(
        title="El monte",
        protagonista="Irene",
        relator="Primera persona. Narrador: Irene.",
        sinopsis="Algo pasa.",
        reglas=["Nadie entra de noche"],
        personajes_full=CAST,
        narrator_config=config or None,
    )


@pytest.fixture(scope="module")
def pb() -> PromptBuilder:
    return PromptBuilder()


def test_narrador_por_nombre_o_por_id(pb):
    assert pb.narrator_name(_story(storyteller_name="Irene")) == "Irene"
    assert pb.narrator_name(_story(storyteller_id="P2")) == "Ricardo"
    assert pb.narrator_name(_story()) == ""


def test_bloque_de_parentescos_desde_la_narradora(pb):
    block = pb._format_kinship(_story(storyteller_id="P1"), "Irene")
    assert block.startswith("\n\nCÓMO LLAMÁS A CADA PERSONAJE (sos Irene):")
    assert "- María: Suegra de Irene; madre de Ricardo" in block
    assert "- Irene:" not in block  # quien narra no se lista
    assert "es tu suegra: no tu madre ni tu abuela" in block


def test_sin_narrador_o_sin_elenco_no_hay_bloque(pb):
    assert pb._format_kinship(_story(), "") == ""
    story = _story(storyteller_name="Irene")
    story.personajes_full = []
    assert pb._format_kinship(story, "Irene") == ""


def test_extras_de_la_voz_guia_clichés_y_parentescos(pb):
    extras = pb._voice_extras(_story(storyteller_name="Irene"))
    assert "OFICIO DE HORROR:" in extras["guia_oficio"]
    assert "«me heló la sangre»" in extras["guia_oficio"]
    assert "Contalos siempre desde vos, Irene" in extras["guia_oficio"]
    assert "CÓMO LLAMÁS A CADA PERSONAJE (sos Irene):" in extras["parentescos"]
    assert "{" not in "".join(extras.values())  # ningún placeholder sin completar


def test_sin_narrador_la_guia_habla_del_narrador(pb):
    extras = pb._voice_extras(_story())
    assert "Contalos siempre desde vos, el narrador" in extras["guia_oficio"]
    assert extras["parentescos"] == ""


def test_presentacion_con_el_nombre_de_quien_narra(pb):
    presentacion = pb._voice_extras(_story(storyteller_name="Irene"))["presentacion"]
    assert presentacion.startswith(
        "Sos Irene y contás en primera persona los hechos de la historia (Primera persona."
    )
    sin = pb._voice_extras(_story())["presentacion"]
    assert "Sos Primera persona. Narrador: Irene., narrando en primera persona" in sin
