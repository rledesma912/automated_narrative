"""Tests unitarios para ResponseNormalizer."""

from src.infrastructure.normalizers import ResponseNormalizer


def _config(**overrides) -> dict:
    base = {
        "thinking_tags": ["think", "reasoning"],
        "strip_line_patterns": [
            r"^#{1,6}\s",
            r"^---+\s*$",
            r"^(Aquí tienes|A continuación|Espero que)",
        ],
        "preserve_paragraph_breaks": True,
        "model_overrides": {
            "natsumura": {
                "strip_line_patterns_extra": [r"^###\s*(Apertura|Desarrollo|Cierre)"],
            }
        },
    }
    base.update(overrides)
    return base


class TestResponseNormalizer:
    def test_strips_thinking_tag_block(self):
        n = ResponseNormalizer(config=_config())
        raw = "<think>razonamiento interno</think>\n\nTexto final."
        assert n.normalize(raw) == "Texto final."

    def test_strips_multiple_thinking_tags_case_insensitive(self):
        n = ResponseNormalizer(config=_config())
        raw = "<THINK>uno</THINK><reasoning>dos</reasoning>Contenido."
        assert n.normalize(raw) == "Contenido."

    def test_strips_markdown_headers(self):
        n = ResponseNormalizer(config=_config())
        raw = "## Título\n\nPárrafo 1.\n\n### Subtítulo\n\nPárrafo 2."
        result = n.normalize(raw)
        assert "Título" not in result
        assert "Subtítulo" not in result
        assert "Párrafo 1." in result
        assert "Párrafo 2." in result

    def test_strips_horizontal_rules(self):
        n = ResponseNormalizer(config=_config())
        raw = "Párrafo 1.\n\n---\n\nPárrafo 2."
        result = n.normalize(raw)
        assert "---" not in result
        assert "Párrafo 1." in result
        assert "Párrafo 2." in result

    def test_strips_preamble_lines(self):
        n = ResponseNormalizer(config=_config())
        raw = "Aquí tienes el beat:\nEl protagonista camina."
        result = n.normalize(raw)
        assert "Aquí tienes" not in result
        assert "El protagonista camina." in result

    def test_preserves_paragraph_breaks(self):
        n = ResponseNormalizer(config=_config())
        raw = "Párrafo 1.\n\nPárrafo 2.\n\nPárrafo 3."
        result = n.normalize(raw)
        assert result == "Párrafo 1.\n\nPárrafo 2.\n\nPárrafo 3."

    def test_collapses_three_or_more_blank_lines(self):
        n = ResponseNormalizer(config=_config())
        raw = "Primero.\n\n\n\n\nSegundo."
        result = n.normalize(raw)
        assert result == "Primero.\n\nSegundo."

    def test_compact_mode_drops_blank_lines(self):
        cfg = _config(preserve_paragraph_breaks=False)
        n = ResponseNormalizer(config=cfg)
        raw = "Línea 1.\n\nLínea 2."
        result = n.normalize(raw)
        assert result == "Línea 1.\nLínea 2."

    def test_model_override_applied_when_model_name_matches(self):
        n = ResponseNormalizer(config=_config())
        raw = "### Apertura\n\nTexto real."
        result = n.normalize(raw, model_name="Tohur/natsumura-storytelling-rp-llama-3.1:8b")
        assert "Apertura" not in result
        assert "Texto real." in result

    def test_model_override_skipped_when_model_name_differs(self):
        cfg = _config(strip_line_patterns=[])
        n = ResponseNormalizer(config=cfg)
        raw = "### Apertura\n\nTexto."
        result = n.normalize(raw, model_name="otro-modelo")
        assert "Apertura" in result

    def test_empty_config_returns_text_unchanged(self):
        n = ResponseNormalizer(config={})
        raw = "Un texto cualquiera."
        assert n.normalize(raw) == "Un texto cualquiera."

    def test_trailing_whitespace_cleaned(self):
        n = ResponseNormalizer(config=_config())
        raw = "Línea con espacios al final   \n\nOtra línea  "
        result = n.normalize(raw)
        assert "   \n" not in result
        assert result.endswith("Otra línea")
