"""Spec-470 S1: guía de oficio, parentescos y primera persona en la Voz."""

import pytest

from src.application.services import PromptBuilder
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.narrative_context_assembler import NarrativeContextAssembler
from src.domain.models import MacroBeat, Story

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


@pytest.mark.parametrize("variant", ["compact", "frontier"])
def test_las_dos_variantes_llevan_guia_clichés_y_parentescos(pb, variant):
    story = _story(storyteller_name="Irene")
    if variant == "compact":
        prompt = pb.build_voice_system_compact(story, 1)
    else:
        prompt = pb.build_voice_prompt(story)
    assert "OFICIO DE HORROR:" in prompt
    assert "«me heló la sangre»" in prompt
    assert "Contalos siempre desde vos, Irene" in prompt
    assert "CÓMO LLAMÁS A CADA PERSONAJE (sos Irene):" in prompt
    assert "{" not in prompt  # ningún placeholder sin completar


def test_build_system_prompt_frontier_tambien_completa_los_placeholders(pb):
    assert "{" not in pb.build_system_prompt(_story(storyteller_name="Irene"))


def test_sin_narrador_la_guia_habla_del_narrador(pb):
    prompt = pb.build_voice_system_compact(_story(), 1)
    assert "Contalos siempre desde vos, el narrador" in prompt
    assert "CÓMO LLAMÁS A CADA PERSONAJE" not in prompt


def test_encabezado_del_evento_con_y_sin_narrador():
    assembler = NarrativeContextAssembler(BeatSpecRepository())
    beat = MacroBeat(number=1, summary="Irene llega.")
    with_narrator = assembler.assemble(beat, {}, narrator="Irene")
    assert with_narrator.startswith(
        "EVENTO DE ESTE MOMENTO (contalo en primera persona, como Irene; "
        "narrá EXACTAMENTE estos eventos, en orden):"
    )
    assert assembler.assemble(beat, {}).startswith(
        "EVENTO DE ESTE MOMENTO (narrá EXACTAMENTE estos eventos, en orden):"
    )


def test_presentacion_con_el_nombre_de_quien_narra(pb):
    prompt = pb.build_voice_system_compact(_story(storyteller_name="Irene"), 1)
    assert (
        "Sos Irene y contás en primera persona los hechos de la historia (Primera persona."
        in prompt
    )
    sin = pb.build_voice_system_compact(_story(), 1)
    assert "Sos Primera persona. Narrador: Irene., narrando en primera persona" in sin
