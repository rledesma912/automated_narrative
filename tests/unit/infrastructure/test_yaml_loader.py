"""Tests para YamlStoryLoader."""

import tempfile
from pathlib import Path

import pytest

from src.infrastructure.loaders import YamlStoryLoader, YamlStoryLoaderError


class TestYamlStoryLoader:
    def test_carga_la_ofrenda(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path("input_stories/la_ofrenda.yaml"))

        assert dto.title == "La ofrenda"
        assert "Ramiro" in dto.protagonista
        assert "Primera" in dto.relator or "primera" in dto.relator
        assert len(dto.sinopsis) > 100

    def test_escenarios_vienen_de_storyteller_config(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path("input_stories/la_ofrenda.yaml"))

        assert len(dto.escenarios) == 4
        assert "El Destacamento de Cuesta del Ternero" in dto.escenarios[0]

    def test_el_monte_prohibido_escenarios(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path("input_stories/el_monte_prohibido.yaml"))

        assert len(dto.escenarios) == 4
        assert dto.escenarios[0] == "Casa de María"

    def test_typed_rules_tiene_content_no_text(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path("input_stories/la_ofrenda.yaml"))

        assert len(dto.typed_rules) > 0
        assert "content" in dto.typed_rules[0]
        assert "text" not in dto.typed_rules[0]

    def test_archivo_inexistente(self):
        loader = YamlStoryLoader()

        with pytest.raises(YamlStoryLoaderError) as exc:
            loader.load_from_file(Path("input_stories/no_existe.yaml"))
        assert "no encontrado" in str(exc.value).lower()

    def test_yaml_vacio(self):
        loader = YamlStoryLoader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            path = Path(f.name)

        with pytest.raises(YamlStoryLoaderError):
            loader.load_from_file(path)

        path.unlink()

    def test_load_from_dict(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_dict(
            {
                "title": "Test",
                "protagonista": "Protagonista",
                "relator": "tercera_persona",
                "sinopsis": "Sinopsis de prueba",
                "atmosfera": "terror",
            }
        )

        assert dto.title == "Test"
        assert dto.protagonista == "Protagonista"
