"""Tests para TemplateLoader — Spec 063 Slice B."""

from pathlib import Path

import pytest

from src.application.services.template_loader import TemplateLoader


@pytest.fixture
def loader(tmp_path: Path) -> TemplateLoader:
    return TemplateLoader(tmp_path)


def _write(tmp_path: Path, name: str, content: str) -> None:
    (tmp_path / name).write_text(content, encoding="utf-8")


class TestTemplateLoaderLoad:
    def test_carga_archivo_existente(self, loader, tmp_path):
        _write(tmp_path, "foo.md", "hola mundo")
        assert loader.load("foo.md") == "hola mundo"

    def test_retorna_vacio_si_no_existe(self, loader):
        assert loader.load("no_existe.md") == ""

    def test_cacheo_no_relee_disco(self, loader, tmp_path):
        _write(tmp_path, "cached.md", "v1")
        loader.load("cached.md")
        (tmp_path / "cached.md").write_text("v2", encoding="utf-8")
        assert loader.load("cached.md") == "v1"

    def test_strip_contenido(self, loader, tmp_path):
        _write(tmp_path, "space.md", "  contenido  \n")
        assert loader.load("space.md") == "contenido"
