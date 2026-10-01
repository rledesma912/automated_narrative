"""Spec-610 T1.3: tiempos del episodio, con los casos compartidos con tiempos.js."""

import json
from pathlib import Path

import pytest

from src.application.services.video import timing

CASOS = json.loads(
    (Path(__file__).resolve().parents[3] / "fixtures" / "video" / "tiempos_casos.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("caso", CASOS["palabras"])
def test_palabras(caso):
    assert timing.palabras(caso["texto"]) == caso["palabras"]


@pytest.mark.parametrize("caso", CASOS["segundos"])
def test_segundos(caso):
    assert timing.segundos(caso["palabras"], caso["ppm"]) == caso["segundos"]


@pytest.mark.parametrize("caso", CASOS["reloj"])
def test_reloj(caso):
    assert timing.reloj(caso["segundos"]) == caso["texto"]


@pytest.mark.parametrize("caso", CASOS["largo"])
def test_largo(caso):
    assert timing.largo(caso["segundos"]) == caso["texto"]


@pytest.mark.parametrize("caso", CASOS["episodio"])
def test_episodio(caso):
    assert timing.episodio(caso["segundos"], caso["desde"], caso["hasta"]) == caso["estado"]
