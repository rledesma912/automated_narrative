"""Tests para helpers de commands.py."""

import re

from src.cli.commands import _write_markdown
from src.domain.models import Beat, Story


def _make_story_with_beats() -> Story:
    story = Story(
        title="El Monte Prohibido",
        protagonista="Ricardo, Irene",
        relator="Irene",
        escenarios="El monte",
        sinopsis="Una familia enfrenta el terror.",
        atmosfera="terror folclórico",
    )
    story.beats = [
        Beat(number=1, summary="s1", content="Prosa del primer acto."),
        Beat(number=2, summary="s2", content="Prosa del segundo acto."),
    ]
    return story


class TestWriteMarkdown:
    def test_crea_archivo_en_output_dir(self, tmp_path):
        story = _make_story_with_beats()
        path = _write_markdown(story, tmp_path)
        assert path.exists()

    def test_archivo_en_directorio_correcto(self, tmp_path):
        story = _make_story_with_beats()
        path = _write_markdown(story, tmp_path)
        assert path.parent == tmp_path

    def test_nombre_contiene_titulo_y_timestamp(self, tmp_path):
        story = _make_story_with_beats()
        path = _write_markdown(story, tmp_path)
        assert "el_monte_prohibido" in path.name
        assert re.search(r"\d{12}", path.name)

    def test_contenido_tiene_titulo(self, tmp_path):
        story = _make_story_with_beats()
        path = _write_markdown(story, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "# El Monte Prohibido" in content

    def test_contenido_tiene_actos(self, tmp_path):
        story = _make_story_with_beats()
        path = _write_markdown(story, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "## Acto 1" in content
        assert "## Acto 2" in content

    def test_contenido_tiene_prosa(self, tmp_path):
        story = _make_story_with_beats()
        path = _write_markdown(story, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "Prosa del primer acto." in content

    def test_crea_output_dir_si_no_existe(self, tmp_path):
        new_dir = tmp_path / "subdir" / "output"
        story = _make_story_with_beats()
        path = _write_markdown(story, new_dir)
        assert path.exists()

    def test_titulo_con_espacios_usa_guion_bajo(self, tmp_path):
        story = _make_story_with_beats()
        story.title = "Mi Historia De Terror"
        path = _write_markdown(story, tmp_path)
        assert "mi_historia_de_terror" in path.name
