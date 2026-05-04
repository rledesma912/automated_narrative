"""Tests for MarkdownRenderer."""

import re

from src.domain.models import Beat, Story
from src.infrastructure.renderers.markdown_renderer import MarkdownRenderer


def _make_story(beats: list[Beat]) -> Story:
    story = Story(
        title="El Monte Prohibido",
        protagonista="Ricardo, Irene",
        relator="Irene",
        escenarios="El monte",
        sinopsis="Una familia enfrenta el terror del monte.",
        atmosfera="terror folclórico",
        reglas=["Regla 1", "Regla 2"],
    )
    story.beats = beats
    return story


class TestMarkdownRenderer:
    def setup_method(self):
        self.renderer = MarkdownRenderer()

    def test_output_starts_with_title(self):
        story = _make_story([])
        result = self.renderer.render(story)
        assert result.startswith("# El Monte Prohibido")

    def test_no_metadata_block(self):
        story = _make_story([])
        result = self.renderer.render(story)
        assert "**Protagonistas:**" not in result
        assert "**Relator:**" not in result
        assert "**Escenario:**" not in result
        assert "**Atmósfera:**" not in result
        assert "**Reglas:**" not in result
        assert "_Una familia" not in result

    def test_no_sinopsis_in_output(self):
        story = _make_story([])
        result = self.renderer.render(story)
        assert "sinopsis" not in result.lower()
        assert story.sinopsis not in result

    def test_beat_headers_are_acto_n(self):
        beats = [
            Beat(number=1, summary="Resumen del beat 1", content="Prosa del acto uno."),
            Beat(number=2, summary="Resumen del beat 2", content="Prosa del acto dos."),
        ]
        story = _make_story(beats)
        result = self.renderer.render(story)
        assert "## Acto 1" in result
        assert "## Acto 2" in result

    def test_beat_summary_not_used_as_header(self):
        beats = [
            Beat(number=1, summary="Resumen largo que no debería aparecer", content="Contenido.")
        ]
        story = _make_story(beats)
        result = self.renderer.render(story)
        assert "Resumen largo que no debería aparecer" not in result

    def test_beat_content_appears_after_header(self):
        beats = [Beat(number=1, summary="Resumen", content="La oscuridad se cernía sobre ellos.")]
        story = _make_story(beats)
        result = self.renderer.render(story)
        acto_pos = result.index("## Acto 1")
        content_pos = result.index("La oscuridad se cernía sobre ellos.")
        assert content_pos > acto_pos

    def test_beats_sorted_by_number(self):
        beats = [
            Beat(number=3, summary="s3", content="Tercero."),
            Beat(number=1, summary="s1", content="Primero."),
            Beat(number=2, summary="s2", content="Segundo."),
        ]
        story = _make_story(beats)
        result = self.renderer.render(story)
        pos1 = result.index("## Acto 1")
        pos2 = result.index("## Acto 2")
        pos3 = result.index("## Acto 3")
        assert pos1 < pos2 < pos3

    def test_duplicate_beat_numbers_rendered_once(self):
        beats = [
            Beat(number=1, summary="s1", content="Primera versión."),
            Beat(number=1, summary="s1b", content="Segunda versión duplicada."),
        ]
        story = _make_story(beats)
        result = self.renderer.render(story)
        assert result.count("## Acto 1") == 1

    def test_header_format_matches_acto_pattern(self):
        beats = [Beat(number=i, summary=f"s{i}", content=f"Contenido {i}.") for i in range(1, 4)]
        story = _make_story(beats)
        result = self.renderer.render(story)
        headers = re.findall(r"^## .+", result, re.MULTILINE)
        for header in headers:
            assert re.match(r"^## Acto \d+$", header), f"Header inesperado: {header!r}"
