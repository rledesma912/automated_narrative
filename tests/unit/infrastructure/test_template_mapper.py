"""Tests para TemplateMapper."""

import pytest

from src.infrastructure.mappers import TemplateInput, TemplateMapper


class TestTemplateMapper:
    """Test suite para TemplateMapper."""

    @pytest.fixture
    def mapper(self):
        return TemplateMapper()

    @pytest.fixture
    def valid_input(self):
        return TemplateInput(
            "La Casa Abandonada",
            "María",
            "tercera_persona",
            "terror psicológico",
            "Una casa abandonada en las afueras",
            "Una familia se muda a una casa embrujada",
            ["No matar personajes principales"],
        )

    def test_map_basic_fields(self, mapper, valid_input):
        """Mapea campos básicos correctamente."""
        story = mapper.map(valid_input)

        assert story.title == "La Casa Abandonada"
        assert story.protagonista == "María"
        assert story.atmosfera == "terror psicológico"
        assert any("abandonada" in s.name.lower() for s in story.scenarios)
        assert story.sinopsis == "Una familia se muda a una casa embrujada"

    def test_map_keeps_spanish_fields(self, mapper, valid_input):
        """Mantiene campos en español para backwards-compatibility."""
        story = mapper.map(valid_input)

        assert story.protagonista == "María"
        assert story.atmosfera == "terror psicológico"
        assert len(story.scenarios) == 1
        assert story.scenarios[0].name == "Una casa abandonada en las afueras"

    def test_map_relator_tercera_persona(self, mapper, valid_input):
        """Mapea relator tercera_persona a third_person."""
        story = mapper.map(valid_input)

        assert story.relator == "third_person"

    def test_map_relator_primera_persona(self, mapper):
        """Mapea relator primera_persona a first_person."""
        input_data = TemplateInput("Test", "Juan", "primera_persona", "misterio", "Bosque", "Test")

        story = mapper.map(input_data)

        assert story.relator == "first_person"

    def test_map_relator_unknown(self, mapper):
        """Mantiene valor original si relator no está en mapping."""
        input_data = TemplateInput("Test", "Juan", "voz_narrador", "misterio", "Bosque", "Test")

        story = mapper.map(input_data)

        assert story.relator == "voz_narrador"

    def test_map_reglas_default(self, mapper):
        """Maneja reglas None con default vacío."""
        input_data = TemplateInput("Test", "Juan", "tercera_persona", "misterio", "Bosque", "Test")

        story = mapper.map(input_data)

        assert story.reglas == []
