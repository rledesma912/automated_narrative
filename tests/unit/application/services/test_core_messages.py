"""Tests de MessageCatalog (Spec-620): mensajes del Core desde `config/core_messages.yaml`."""

from pathlib import Path

import pytest

from src.application.services.core_messages import MessageCatalog


@pytest.fixture
def catalog(tmp_path: Path) -> MessageCatalog:
    path = tmp_path / "core_messages.yaml"
    path.write_text(
        "workshop:\n"
        "  listo: Ya podés armar los actos.\n"
        "  quedan_varios: Te quedan {n} preguntas.\n",
        encoding="utf-8",
    )
    return MessageCatalog(path)


def test_mensaje_por_clave_con_puntos(catalog):
    assert catalog.get("workshop.listo") == "Ya podés armar los actos."


def test_formatea_con_los_datos(catalog):
    assert catalog.get("workshop.quedan_varios", n=3) == "Te quedan 3 preguntas."


@pytest.mark.parametrize("key", ["workshop.no_existe", "otra.area", "workshop"])
def test_clave_inexistente_o_que_no_es_mensaje_es_error(catalog, key):
    with pytest.raises(KeyError):
        catalog.get(key)


def test_dato_faltante_es_error(catalog):
    with pytest.raises(KeyError, match="n"):
        catalog.get("workshop.quedan_varios")


def test_el_catalogo_real_carga():
    MessageCatalog()  # el YAML de config/ es válido
