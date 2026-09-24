"""Spec-450 §10: manifestaciones según el acto, con los textos reales de «El monte prohibido»."""

from pathlib import Path

import pytest
import yaml

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.manifestations import (
    manifestations_for_act,
    reserved_act,
    split_manifestations,
)
from src.application.services.narrative_context_assembler import NarrativeContextAssembler
from src.domain.models import Entity, MacroBeat, RevealLevel

STORY = yaml.safe_load(
    (Path(__file__).parents[3] / "input_stories" / "el_monte_prohibido.yaml").read_text("utf-8")
)
ACTS = [STORY["storyteller_config"]["actos"][f"act_{n}"]["text"] for n in range(1, 6)]
SOMBRA = (
    "El caballo se clava de golpe; una figura idéntica a María que no parpadea; "
    "olor a tierra mojada; un silencio que apaga los grillos."
)
MONTE = (
    "El camino se deforma; los mismos espinillos retorcidos aparecen una y otra vez; "
    "las espinas se enganchan en la ropa."
)


def test_split():
    assert split_manifestations("Uno; dos. Tres.") == ["Uno", "dos", "Tres"]
    assert split_manifestations("") == []


@pytest.mark.parametrize(
    ("item", "act"),
    [
        ("El caballo se clava de golpe", 3),
        ("una figura idéntica a María que no parpadea", 3),
        ("El camino se deforma", 4),
        ("los mismos espinillos retorcidos aparecen una y otra vez", 4),
        ("las espinas se enganchan en la ropa", 5),
        ("olor a tierra mojada", None),
        ("un silencio que apaga los grillos", None),
    ],
)
def test_cada_manifestacion_queda_reservada_para_su_acto(item, act):
    assert reserved_act(item, ACTS) == act


def test_acto_1_solo_senales_libres():
    assert manifestations_for_act(SOMBRA, 1, ACTS, 2) == [
        "olor a tierra mojada",
        "un silencio que apaga los grillos",
    ]
    assert manifestations_for_act(MONTE, 1, ACTS, 2) == []  # todo es de actos posteriores


def test_primero_las_del_acto_y_respeta_el_tope():
    assert manifestations_for_act(SOMBRA, 3, ACTS, 3) == [
        "El caballo se clava de golpe",
        "una figura idéntica a María que no parpadea",
        "olor a tierra mojada",
    ]
    assert manifestations_for_act(SOMBRA, 3, ACTS, 1) == ["El caballo se clava de golpe"]


def _entity(manifestations: str, level: RevealLevel) -> Entity:
    from uuid import uuid4

    return Entity(
        story_id=uuid4(),
        order_index=0,
        name="La Sombra del Monte",
        nature_id="folklorica",
        manifestations=manifestations,
        reveal_level=level,
    )


def _amenaza(beat: int, entity: Entity) -> str:
    context = NarrativeContextAssembler(BeatSpecRepository()).assemble(
        MacroBeat(number=beat, summary="Algo pasa."), {}, entities=[entity], act_texts=ACTS
    )
    return context.split("AMENAZA EN ESTE ACTO")[1].split("\n\n")[0]


def test_la_voz_no_recibe_manifestaciones_de_actos_posteriores():
    block = _amenaza(1, _entity(MONTE, RevealLevel.PROGRESIVA))  # acto 1: señales
    assert "deforma" not in block and "espinillos" not in block
    block = _amenaza(1, _entity(SOMBRA, RevealLevel.INSINUADA))
    assert "Cómo se percibe: olor a tierra mojada; un silencio que apaga los grillos" in block


def test_exposicion_plena_muestra_todas():
    block = _amenaza(4, _entity(MONTE, RevealLevel.PROGRESIVA))  # acto 4: presencia plena
    assert f"Cómo se percibe: {MONTE}" in block
