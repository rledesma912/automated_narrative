"""Spec-610 T3.1: el paquete frente al relato corregido y las marcas que se mueven."""

import json
from pathlib import Path

import pytest

from src.application.services.video.script_builder import narrative_hash
from src.application.services.video.state import relocate, state
from src.domain.video import Mark, PresenterLines, VideoScript

CASOS = json.loads(
    (Path(__file__).resolve().parents[3] / "fixtures" / "video" / "marcas_casos.json").read_text(
        encoding="utf-8"
    )
)
CONTENT = "## Acto 1\n\nUno.\n\nDos.\n\n## Acto 2\n\nTres."


def _script() -> VideoScript:
    import uuid

    return VideoScript(
        narrative_id=uuid.uuid4(),
        bloques=[],
        momentos=[],
        calabaza=PresenterLines(intro="", outro=""),
        parrafos_por_acto={1: 2, 2: 1},
        narrative_hash=narrative_hash(CONTENT),
        seed=1,
    )


def test_al_dia():
    assert state(_script(), CONTENT).as_dict() == {"estado": "al_dia", "actos": []}


def test_cambio_el_texto_sin_cambiar_parrafos():
    content = CONTENT.replace("Dos.", "Dos, corregido.")
    assert state(_script(), content).as_dict() == {"estado": "cambio_el_texto", "actos": []}


def test_cambiaron_los_parrafos_de_un_acto():
    content = CONTENT.replace("Tres.", "Tres.\n\nCuatro.")
    assert state(_script(), content).as_dict() == {"estado": "cambiaron_parrafos", "actos": [2]}


@pytest.mark.parametrize("caso", CASOS["reubicar"], ids=lambda c: c["nombre"])
def test_reubicar_marcas(caso):
    marks = [Mark(**m) for m in caso["marcas"]]
    kept, lost = relocate(caso["palabras"], marks)
    assert [m.model_dump() for m in kept] == caso["quedan"]
    assert lost == caso["perdidas"]
