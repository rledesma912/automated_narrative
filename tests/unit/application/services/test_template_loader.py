"""Tests para TemplateLoader — Spec 063 Slice B."""

from pathlib import Path
from unittest.mock import patch

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


class TestTemplateLoaderVariant:
    def test_variante_compact(self, loader):
        with patch("src.application.services.template_loader.settings") as m:
            m.active_profile_config.return_value = {"prompt_variant": "compact"}
            assert loader.get_variant() == "compact"

    def test_variante_frontier(self, loader):
        with patch("src.application.services.template_loader.settings") as m:
            m.active_profile_config.return_value = {"prompt_variant": "frontier"}
            assert loader.get_variant() == "frontier"

    def test_variante_default_frontier(self, loader):
        with patch("src.application.services.template_loader.settings") as m:
            m.active_profile_config.return_value = {}
            assert loader.get_variant() == "frontier"


class TestTemplateLoaderVoiceTemplateName:
    def test_compact_con_archivo_existente(self, loader, tmp_path):
        _write(tmp_path, "voice_compact.md", "x")
        with patch("src.application.services.template_loader.settings") as m:
            m.active_profile_config.return_value = {"prompt_variant": "compact"}
            assert loader.voice_template_name() == "voice_compact.md"

    def test_compact_sin_archivo_usa_fallback(self, loader, tmp_path):
        with patch("src.application.services.template_loader.settings") as m:
            m.active_profile_config.return_value = {"prompt_variant": "compact"}
            m.prompt_file_voice = "voice.md"
            assert loader.voice_template_name() == "voice.md"

    def test_frontier_usa_settings(self, loader):
        with patch("src.application.services.template_loader.settings") as m:
            m.active_profile_config.return_value = {"prompt_variant": "frontier"}
            m.prompt_file_voice = "voice.md"
            assert loader.voice_template_name() == "voice.md"
