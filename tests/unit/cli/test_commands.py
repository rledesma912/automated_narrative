"""Tests para helpers de commands.py."""

import re

from src.cli.commands import _write_markdown
from src.domain.models import Beat, Story


def _make_renderer():
    class _Renderer:
        def render(self, story):
            parts = [f"# {story.title}", ""]
            for beat in story.beats:
                parts.extend([f"## Acto {beat.number}", beat.content, ""])
            return "\n".join(parts)

    return _Renderer()


def _make_story_with_beats() -> Story:
    story = Story(
        title="El Monte Prohibido",
        protagonista="Ricardo, Irene",
        relator="Irene",
        sinopsis="Una familia enfrenta el terror.",
        atmosfera="terror folclórico",
    )
    story.beats = [
        Beat(number=1, summary="s1", content="Prosa del primer acto."),
        Beat(number=2, summary="s2", content="Prosa del segundo acto."),
    ]
    return story


class TestWriteMarkdown:
    def test_crea_archivo_con_nombre_sanitizado_y_timestamp(self, tmp_path):
        story = _make_story_with_beats()
        path = _write_markdown(story, tmp_path, _make_renderer())
        assert path.exists()
        assert path.parent == tmp_path
        assert "el_monte_prohibido" in path.name
        assert re.search(r"\d{12}", path.name)

    def test_contenido_incluye_titulo_y_beats(self, tmp_path):
        story = _make_story_with_beats()
        path = _write_markdown(story, tmp_path, _make_renderer())
        content = path.read_text(encoding="utf-8")
        assert "# El Monte Prohibido" in content
        assert "## Acto 1" in content
        assert "## Acto 2" in content
        assert "Prosa del primer acto." in content

    def test_crea_output_dir_si_no_existe(self, tmp_path):
        new_dir = tmp_path / "subdir" / "output"
        story = _make_story_with_beats()
        path = _write_markdown(story, new_dir, _make_renderer())
        assert path.exists()

    def test_titulo_con_espacios_usa_guion_bajo(self, tmp_path):
        story = _make_story_with_beats()
        story.title = "Mi Historia De Terror"
        path = _write_markdown(story, tmp_path, _make_renderer())
        assert "mi_historia_de_terror" in path.name
