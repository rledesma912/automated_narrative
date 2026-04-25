"""Tests para StoryAnalystService (Spec-038, criterio B5)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services import PromptBuilder, StoryAnalystService
from src.domain.models import NarrativeAnchors, Story


def _make_story(**kwargs):
    defaults = dict(
        title="El Monte Prohibido",
        protagonista="Irene, Ricardo",
        relator="Irene",
        escenarios="Monte de los Espinillos",
        sinopsis="La familia llega al campo. Entran al monte de noche. Ven la figura de María inmóvil.",
        atmosfera="terror paranormal",
    )
    defaults.update(kwargs)
    return Story(**defaults)


def _make_llm(response_text: str):
    llm = AsyncMock()
    resp = MagicMock()
    resp.text = response_text
    resp.elapsed_s = 0.5
    llm.generate = AsyncMock(return_value=resp)
    return llm


_VALID_MARKDOWN = """\
## initial_state
Irene llega tranquila, sin sospechar nada.

## threat_nature
Una presencia que imita a los conocidos para atraer.

## horror_peak
La figura de María inmóvil en el claro del monte.

## spatial_anchor
Monte de los Espinillos: espinillos cerrados, relámpagos.
"""


class TestExtractAnchors:
    """B5 — extract_anchors() retorna NarrativeAnchors (no texto libre)."""

    @pytest.mark.asyncio
    async def test_returns_narrative_anchors_object(self):
        llm = _make_llm(_VALID_MARKDOWN)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert isinstance(result, NarrativeAnchors)

    @pytest.mark.asyncio
    async def test_all_four_fields_populated(self):
        llm = _make_llm(_VALID_MARKDOWN)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert result.initial_state != ""
        assert result.threat_nature != ""
        assert result.horror_peak != ""
        assert result.spatial_anchor != ""

    @pytest.mark.asyncio
    async def test_story_id_matches(self):
        llm = _make_llm(_VALID_MARKDOWN)
        service = StoryAnalystService(llm, PromptBuilder())
        story = _make_story()
        result = await service.extract_anchors(story)
        assert result.story_id == story.id

    @pytest.mark.asyncio
    async def test_values_match_sections(self):
        llm = _make_llm(_VALID_MARKDOWN)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert "Irene" in result.initial_state
        assert "Monte de los Espinillos" in result.spatial_anchor

    @pytest.mark.asyncio
    async def test_uses_story_analyst_role(self):
        llm = _make_llm(_VALID_MARKDOWN)
        service = StoryAnalystService(llm, PromptBuilder())
        await service.extract_anchors(_make_story())
        call_kwargs = llm.generate.call_args.kwargs
        assert call_kwargs.get("role") == "story_analyst"

    @pytest.mark.asyncio
    async def test_multiline_section_value(self):
        """El valor de una sección puede ocupar múltiples líneas."""
        response = (
            "## initial_state\n"
            "Irene llega tranquila.\n"
            "No sospecha nada todavía.\n\n"
            "## threat_nature\nUna presencia imitadora.\n\n"
            "## horror_peak\nFigura inmóvil en el claro.\n\n"
            "## spatial_anchor\nEspinillos, barro, relámpagos.\n"
        )
        llm = _make_llm(response)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert "No sospecha nada todavía" in result.initial_state

    @pytest.mark.asyncio
    async def test_preamble_text_before_sections_ignored(self):
        """Texto libre antes de las secciones ## no interfiere."""
        response = "Aquí están los anclajes:\n\n" + _VALID_MARKDOWN
        llm = _make_llm(response)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert isinstance(result, NarrativeAnchors)
        assert result.initial_state != ""


class TestFallbackAnchors:
    """extract_anchors() aplica fallback cuando el LLM devuelve formato inválido."""

    @pytest.mark.asyncio
    async def test_fallback_on_missing_sections(self):
        """Si el LLM devuelve texto sin secciones ##, retorna NarrativeAnchors con fallback."""
        llm = _make_llm("No sé qué responder.")
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert isinstance(result, NarrativeAnchors)
        assert result.initial_state != ""

    @pytest.mark.asyncio
    async def test_fallback_on_partial_sections(self):
        """Si solo hay algunas secciones, los campos faltantes usan sinopsis como fallback."""
        partial = "## initial_state\nIrene llega.\n\n## threat_nature\nUna presencia."
        llm = _make_llm(partial)
        service = StoryAnalystService(llm, PromptBuilder())
        story = _make_story()
        result = await service.extract_anchors(story)
        assert result.initial_state == "Irene llega."
        assert result.horror_peak != ""  # fallback con sinopsis

    @pytest.mark.asyncio
    async def test_fallback_never_raises(self):
        """Un response completamente vacío devuelve NarrativeAnchors sin lanzar excepción."""
        llm = _make_llm("")
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert isinstance(result, NarrativeAnchors)
        assert result.initial_state != ""


class TestResolveAnchors:
    """resolve_beat_anchors() delega correctamente al domain function."""

    def test_delegating_to_domain_function(self):
        llm = MagicMock()
        service = StoryAnalystService(llm, PromptBuilder())
        anchors = NarrativeAnchors(
            story_id=uuid.uuid4(),
            initial_state="Estado A",
            threat_nature="Amenaza B",
            horror_peak="Pico C",
            spatial_anchor="Espacio D",
        )
        result = service.resolve_beat_anchors(anchors, 1)
        assert result["principal"] == "Estado A"
        assert result["contexto"] == "Espacio D"

    def test_climax_beat_returns_horror_peak(self):
        llm = MagicMock()
        service = StoryAnalystService(llm, PromptBuilder())
        anchors = NarrativeAnchors(
            story_id=uuid.uuid4(),
            initial_state="A",
            threat_nature="B",
            horror_peak="La figura inmóvil",
            spatial_anchor="D",
        )
        result = service.resolve_beat_anchors(anchors, 3)
        assert result["principal"] == "La figura inmóvil"
