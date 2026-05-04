"""Tests unitarios para ResponseNormalizer (Spec 044)."""

from src.infrastructure.normalizers import ResponseNormalizer


def _config(**overrides) -> dict:
    base = {
        "thinking_tags": ["think", "reasoning"],
        "strip_line_patterns": [
            r"^(Aquí tienes|A continuación|Espero que)",
            r"^Por supuesto",
            r"^Claro[,!.]",
        ],
        "preserve_paragraph_breaks": True,
        "model_overrides": {
            "deepseek-r1": {"strip_thinking": True},
            "natsumura": {"strip_thinking": False},
        },
    }
    base.update(overrides)
    return base


class TestResponseNormalizerThinkingTags:
    def test_strips_thinking_tag_block(self):
        n = ResponseNormalizer(config=_config())
        raw = "<think>razonamiento interno</think>\n\nTexto final."
        assert n.normalize(raw) == "Texto final."

    def test_strips_multiple_thinking_tags_case_insensitive(self):
        n = ResponseNormalizer(config=_config())
        raw = "<THINK>uno</THINK><reasoning>dos</reasoning>Contenido."
        assert n.normalize(raw) == "Contenido."

    def test_strips_multiline_thinking_block(self):
        n = ResponseNormalizer(config=_config())
        raw = "<think>\nLínea 1\nLínea 2\n</think>\n\nRespuesta real."
        assert n.normalize(raw) == "Respuesta real."


class TestResponseNormalizerPreambles:
    def test_strips_aqui_tienes(self):
        n = ResponseNormalizer(config=_config())
        raw = "Aquí tienes el beat:\nEl protagonista camina."
        result = n.normalize(raw)
        assert "Aquí tienes" not in result
        assert "El protagonista camina." in result

    def test_strips_por_supuesto(self):
        n = ResponseNormalizer(config=_config())
        raw = "Por supuesto, aquí va el relato:\nEra una noche oscura."
        result = n.normalize(raw)
        assert "Por supuesto" not in result
        assert "Era una noche oscura." in result

    def test_strips_espero_que(self):
        n = ResponseNormalizer(config=_config())
        raw = "Era oscuro.\n\nEspero que te guste."
        result = n.normalize(raw)
        assert "Espero que" not in result
        assert "Era oscuro." in result


class TestResponseNormalizerPreservesMarkdown:
    def test_preserves_markdown_headers(self):
        n = ResponseNormalizer(config=_config())
        raw = "## Título\n\nPárrafo 1.\n\n### Subtítulo\n\nPárrafo 2."
        result = n.normalize(raw)
        assert "## Título" in result
        assert "### Subtítulo" in result
        assert "Párrafo 1." in result
        assert "Párrafo 2." in result

    def test_preserves_horizontal_rules(self):
        n = ResponseNormalizer(config=_config())
        raw = "Párrafo 1.\n\n---\n\nPárrafo 2."
        result = n.normalize(raw)
        assert "---" in result
        assert "Párrafo 1." in result
        assert "Párrafo 2." in result

    def test_preserves_code_fences(self):
        n = ResponseNormalizer(config=_config())
        raw = 'Instrucción:\n\n```json\n{"key": "value"}\n```'
        result = n.normalize(raw)
        assert "```json" in result
        assert "```" in result


class TestResponseNormalizerWhitespace:
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

    def test_trailing_whitespace_cleaned(self):
        n = ResponseNormalizer(config=_config())
        raw = "Línea con espacios al final   \n\nOtra línea  "
        result = n.normalize(raw)
        assert "   \n" not in result
        assert result.endswith("Otra línea")


class TestResponseNormalizerEdgeCases:
    def test_empty_config_returns_text_unchanged(self):
        n = ResponseNormalizer(config={})
        raw = "Un texto cualquiera."
        assert n.normalize(raw) == "Un texto cualquiera."

    def test_no_noise_returns_text_unchanged(self):
        n = ResponseNormalizer(config=_config())
        raw = "El bosque respiraba. Las ramas crujían.\n\nAlgo se movía entre los árboles."
        assert n.normalize(raw) == raw

    def test_thinking_tag_plus_preamble_both_stripped(self):
        n = ResponseNormalizer(config=_config())
        raw = "<think>plan</think>\nAquí tienes la respuesta:\nContenido real."
        result = n.normalize(raw)
        assert "<think>" not in result
        assert "Aquí tienes" not in result
        assert "Contenido real." in result
