"""Tests para MarkdownStoryParser."""

import pytest

from src.infrastructure.parsers import MarkdownStoryParser


class TestMarkdownStoryParser:
    """Test suite para MarkdownStoryParser."""

    @pytest.fixture
    def parser(self):
        return MarkdownStoryParser()

    def test_extract_field_basic(self, parser):
        """Extrae campo correctamente."""
        content = "**Protagonistas**: Juan, Pedro\n**Sinopsis**: Una historia"
        result = parser._extract_field(content, "Protagonistas", "**Sinopsis**")
        assert "Juan" in result
        assert "Pedro" in result

    def test_extract_field_not_found(self, parser):
        """Maneja campo no encontrado."""
        content = "**Protagonistas**: Juan"
        result = parser._extract_field(content, "NoExiste", "**Sinopsis**")
        assert result == ""

    def test_normalize_relator_primera(self, parser):
        """Normaliza relator primera persona."""
        assert parser._normalize_relator("primera_persona") == "primera_persona"
        assert parser._normalize_relator("primera") == "primera_persona"
        assert parser._normalize_relator("1ra") == "primera_persona"
        assert parser._normalize_relator("Irene") == "Irene"  # Mantiene nombre específico

    def test_normalize_relator_specific_name(self, parser):
        """Mantiene nombres de personajes específicos."""
        assert parser._normalize_relator("Irene") == "Irene"
        assert parser._normalize_relator("Ricardo") == "Ricardo"
        assert parser._normalize_relator("Mariano") == "Mariano"

    def test_normalize_relator_tercera(self, parser):
        """Normaliza relator tercera persona."""
        assert parser._normalize_relator("tercera_persona") == "tercera_persona"
        assert parser._normalize_relator("tercera") == "tercera_persona"
        assert parser._normalize_relator("3ra") == "tercera_persona"

    def test_extract_list(self, parser):
        """Extrae lista de reglas."""
        content = """## Las reglas de la historia

- Regla 1
- Regla 2
- Regla 3

---
"""
        reglas = parser._extract_list(content, "Las reglas de la historia")
        assert reglas == ["Regla 1", "Regla 2", "Regla 3"]

    def test_extract_list_empty(self, parser):
        """Maneja lista vacía."""
        content = "Sin reglas aquí"
        reglas = parser._extract_list(content, "Las reglas de la historia")
        assert reglas == []

    def test_extract_data_complete(self, parser):
        """Extrae todos los datos del markdown."""
        content = """# Contexto del relato

**Protagonistas**: Ricardo 35 padre
Irene 34 madre
**relator**: Irene
**Escenarios**: Casa de campo
**Sinopsis**: Una familia en peligro

---

## Las reglas de la historia

- No matar personajes
- Mantener tensión

---

**Acto 1**
Contenido del acto
"""
        data = parser._extract_data(content, "el_monte_prohibido")

        assert data.title == "el_monte_prohibido"
        assert "Ricardo" in data.protagonista
        assert data.relator == "Irene"  # Mantiene nombre específico
        assert "casa" in data.escenarios.lower()
        assert "familia" in data.sinopsis.lower()
        assert "No matar" in data.reglas[0]

    def test_parse_el_monte_prohibido_completo(self):
        """Verifica que el archivo real mapea correctamente todos los campos (tarea 4.2 spec 017)."""
        from pathlib import Path
        parser = MarkdownStoryParser(input_dir=Path("input_stories"))
        data = parser.parse("el_monte_prohibido.md")

        assert data.title == "El Monte Prohibido"
        assert "Ricardo" in data.protagonista
        assert "Irene" in data.protagonista
        assert "Mariano" in data.protagonista
        assert data.relator == "Irene"
        assert "monte" in data.escenarios.lower()
        assert len(data.sinopsis) > 100
        assert "Monte de los Espinillos" in data.sinopsis
        assert len(data.reglas) == 5
        assert any("Ricardo" in r for r in data.reglas)
        assert any("Irene" in r for r in data.reglas)
        assert data.atmosfera != ""
        assert "terror" in data.atmosfera.lower()

    def test_parse_file_not_found(self, parser):
        """Maneja archivo no encontrado."""
        with pytest.raises(FileNotFoundError):
            parser.parse("no_existe.md")

    def test_clean_markdown_bold(self, parser):
        """Limpia ** del markdown."""
        assert parser._clean_markdown("**texto**") == "texto"
        assert parser._clean_markdown("**Protagonistas**: Juan") == "Protagonistas: Juan"

    def test_clean_markdown_italic(self, parser):
        """Limpia * del markdown."""
        assert parser._clean_markdown("*texto*") == "texto"

    def test_clean_markdown_headers(self, parser):
        """Limpia headers # del markdown."""
        assert parser._clean_markdown("# Título") == "Título"
        assert parser._clean_markdown("## Subtítulo") == "Subtítulo"

    def test_clean_markdown_list_items(self, parser):
        """Limpia items de lista del markdown."""
        assert parser._clean_markdown("- Item 1") == "Item 1"
        assert parser._clean_markdown("* Item 2") == "Item 2"

    def test_clean_markdown_combined(self, parser):
        """Limpia combinación de markdown."""
        input_text = "**Protagonistas**: Ricardo 35 padre,\nIrene 34 madre"
        expected = "Protagonistas: Ricardo 35 padre,\nIrene 34 madre"
        assert parser._clean_markdown(input_text) == expected
