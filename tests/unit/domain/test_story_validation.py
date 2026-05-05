"""Tests para validación de Story y StoryCreateDTO."""

import pytest
from pydantic import ValidationError

from src.application.dto import StoryCreateDTO
from src.domain.models import Story


class TestStoryValidation:
    def test_rechaza_titulo_vacio(self):
        with pytest.raises(ValidationError) as exc:
            Story(title="", protagonista="p", relator="r", sinopsis="s", atmosfera="a")
        assert "title" in str(exc.value)

    def test_rechaza_protagonista_vacio(self):
        with pytest.raises(ValidationError) as exc:
            Story(title="t", protagonista="", relator="r", sinopsis="s", atmosfera="a")
        assert "protagonista" in str(exc.value)

    def test_rechaza_relator_vacio(self):
        with pytest.raises(ValidationError) as exc:
            Story(title="t", protagonista="p", relator="", sinopsis="s", atmosfera="a")
        assert "relator" in str(exc.value)

    def test_rechaza_sinopsis_vacia(self):
        with pytest.raises(ValidationError) as exc:
            Story(title="t", protagonista="p", relator="r", sinopsis="", atmosfera="a")
        assert "sinopsis" in str(exc.value)

    def test_rechaza_atmosfera_vacia(self):
        with pytest.raises(ValidationError) as exc:
            Story(title="t", protagonista="p", relator="r", sinopsis="s", atmosfera="")
        assert "atmosfera" in str(exc.value)

    def test_rechaza_solo_espacios(self):
        with pytest.raises(ValidationError) as exc:
            Story(title="   ", protagonista="p", relator="r", sinopsis="s", atmosfera="a")
        assert "title" in str(exc.value)

    def test_acepta_campos_validos(self):
        story = Story(
            title="Test",
            protagonista="Protagonista",
            relator="tercera_persona",
            sinopsis="Sinopsis",
            atmosfera="terror",
        )
        assert story.title == "Test"

    def test_normaliza_espacios(self):
        story = Story(title="  Test  ", protagonista="p", relator="r", sinopsis="s", atmosfera="a")
        assert story.title == "Test"


class TestStoryCreateDTOValidation:
    def test_rechaza_titulo_vacio(self):
        with pytest.raises(ValidationError) as exc:
            StoryCreateDTO(title="", protagonista="p", relator="r", sinopsis="s", atmosfera="a")
        assert "title" in str(exc.value)

    def test_rechaza_sinopsis_vacia(self):
        with pytest.raises(ValidationError) as exc:
            StoryCreateDTO(title="t", protagonista="p", relator="r", sinopsis="", atmosfera="a")
        assert "sinopsis" in str(exc.value)

    def test_acepta_campos_validos(self):
        dto = StoryCreateDTO(
            title="Test",
            protagonista="Protagonista",
            relator="tercera_persona",
            sinopsis="Sinopsis",
            atmosfera="terror",
        )
        assert dto.title == "Test"

    def test_normaliza_espacios(self):
        dto = StoryCreateDTO(
            title="  Test  ", protagonista="p", relator="r", sinopsis="s", atmosfera="a"
        )
        assert dto.title == "Test"
