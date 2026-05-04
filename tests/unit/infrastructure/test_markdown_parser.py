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
        result = parser._extract_inline_field(content, "Protagonistas")
        assert "Juan" in result
        assert "Pedro" in result

    def test_extract_field_not_found(self, parser):
        """Maneja campo no encontrado."""
        content = "**Protagonistas**: Juan"
        result = parser._extract_inline_field(content, "NoExiste")
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
        data = parser._extract_data_via_regex(content, "el_monte_prohibido")

        assert data.title == "el_monte_prohibido"
        assert "Ricardo" in data.protagonista
        assert data.relator == "Irene"  # Mantiene nombre específico
        assert any("casa" in s.lower() for s in data.cronologic_scenarios)
        assert "familia" in data.sinopsis.lower()
        assert "No matar" in data.reglas[0]

    def test_parse_el_monte_prohibido_completo(self):
        """Verifica que el archivo real mapea correctamente todos los campos (Spec-043: nuevo formato)."""
        from pathlib import Path

        parser = MarkdownStoryParser(input_dir=Path("input_stories"))
        data = parser.parse("el_monte_prohibido.md")

        # Título desde story.title (nuevo formato)
        assert "monte" in data.title.lower()
        # Protagonista resuelta desde protagonists[role=protagonista]
        assert data.protagonista == "Irene"
        assert data.relator == "Irene"
        # Escenarios: el nuevo archivo tiene 4 escenarios
        assert any("monte" in s.lower() for s in data.cronologic_scenarios)
        # Sinopsis: concatenación de los 5 actos
        assert len(data.sinopsis) > 100
        assert len(data.reglas) >= 1  # el archivo tiene 1 regla
        # Nuevos campos Spec-043
        assert len(data.typed_rules) == len(data.reglas)
        assert all(r.get("type") for r in data.typed_rules)
        assert data.atmosfera != ""
        assert len(data.storyteller_config) > 0

    def test_parse_cronologic_scenarios_list(self, parser):
        """_parse_cronologic_scenarios devuelve lista desde YAML list."""
        data = {"cronologic_scenarios": ["Casa de la abuela", "La fiesta", "El monte"]}
        result = parser._parse_cronologic_scenarios(data)
        assert result == ["Casa de la abuela", "La fiesta", "El monte"]

    def test_parse_cronologic_scenarios_block_string(self, parser):
        """_parse_cronologic_scenarios parsea bloque `|` con ítems `- nombre`."""
        data = {"cronologic_scenarios": "- La casa de campo\n- El monte prohibido\n"}
        result = parser._parse_cronologic_scenarios(data)
        assert result == ["La casa de campo", "El monte prohibido"]

    def test_parse_cronologic_scenarios_empty(self, parser):
        result = parser._parse_cronologic_scenarios({})
        assert result == []

    def test_parse_el_monte_prohibido_cronologic_scenarios(self):
        """El archivo real devuelve los escenarios cronológicos como lista (Spec-043: 4 escenarios)."""
        from pathlib import Path

        parser = MarkdownStoryParser(input_dir=Path("input_stories"))
        data = parser.parse("el_monte_prohibido.md")
        assert len(data.cronologic_scenarios) == 4
        # Verificar que los nombres reales del archivo están presentes
        scenarios_lower = [s.lower() for s in data.cronologic_scenarios]
        assert any("monte" in s for s in scenarios_lower)
        assert any("maría" in s or "maria" in s for s in scenarios_lower)

    def test_parse_file_not_found(self, parser):
        """Maneja archivo no encontrado."""
        with pytest.raises(FileNotFoundError):
            parser.parse("no_existe.md")

    def test_extract_inline_strips_bold_markers(self, parser):
        """_extract_inline_field extrae el valor sin ** del formato **Campo**: valor."""
        content = "**Protagonistas**: Ricardo 35 padre"
        result = parser._extract_inline_field(content, "Protagonistas")
        assert result == "Ricardo 35 padre"

    def test_extract_inline_multiline_value(self, parser):
        """_extract_inline_field captura valor hasta el siguiente campo.**"""
        content = (
            "**Protagonistas**: Ricardo 35 padre\nIrene 34 madre\n\n**Sinopsis**: Una historia"
        )
        result = parser._extract_inline_field(content, "Protagonistas")
        assert "Ricardo" in result
