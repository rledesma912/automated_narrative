"""Tests para StoryAnalystService (Spec-081 — 5 pilares de resonancia narrativa)."""

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
## resonance_hamartia
Irene carga con la culpa silenciosa de no haber creído a su madre.

## resonance_hybris
La familia ignora la advertencia de no entrar al monte de noche.

## resonance_anagnorisis
La figura de María inmóvil en el claro del monte, mirándolos sin parpadear.

## resonance_peripeteia
Monte de los Espinillos: espinillos cerrados, barro que succiona, relámpagos sin trueno.

## resonance_residual
Irene ya no puede cerrar los ojos sin ver el claro iluminado.
"""


class TestExtractAnchors:
    """B5 — extract_anchors() retorna NarrativeAnchors con 5 pilares de resonancia."""

    @pytest.mark.asyncio
    async def test_returns_narrative_anchors_object(self):
        llm = _make_llm(_VALID_MARKDOWN)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert isinstance(result, NarrativeAnchors)

    @pytest.mark.asyncio
    async def test_all_five_fields_populated(self):
        llm = _make_llm(_VALID_MARKDOWN)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert result.resonance_hamartia != ""
        assert result.resonance_hybris != ""
        assert result.resonance_anagnorisis != ""
        assert result.resonance_peripeteia != ""
        assert result.resonance_residual != ""

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
        assert "culpa" in result.resonance_hamartia
        assert "Monte de los Espinillos" in result.resonance_peripeteia

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
            "## resonance_hamartia\n"
            "Irene carga con la culpa.\n"
            "No lo dice nunca.\n\n"
            "## resonance_hybris\nEntran al monte de noche.\n\n"
            "## resonance_anagnorisis\nFigura inmóvil en el claro.\n\n"
            "## resonance_peripeteia\nEspinillos, barro, relámpagos.\n\n"
            "## resonance_residual\nYa no puede dormir.\n"
        )
        llm = _make_llm(response)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert "No lo dice nunca" in result.resonance_hamartia

    @pytest.mark.asyncio
    async def test_preamble_text_before_sections_ignored(self):
        """Texto libre antes de las secciones ## no interfiere."""
        response = "Aquí están los anclajes:\n\n" + _VALID_MARKDOWN
        llm = _make_llm(response)
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert isinstance(result, NarrativeAnchors)
        assert result.resonance_hamartia != ""


class TestFallbackAnchors:
    """extract_anchors() aplica fallback cuando el LLM devuelve formato inválido."""

    @pytest.mark.asyncio
    async def test_fallback_on_missing_sections(self):
        """Si el LLM devuelve texto sin secciones ##, retorna NarrativeAnchors con fallback."""
        llm = _make_llm("No sé qué responder.")
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert isinstance(result, NarrativeAnchors)
        assert result.resonance_hamartia != ""

    @pytest.mark.asyncio
    async def test_fallback_on_partial_sections(self):
        """Si solo hay algunas secciones, los campos faltantes usan sinopsis como fallback."""
        partial = "## resonance_hamartia\nLa culpa callada.\n\n## resonance_hybris\nEntran de noche."
        llm = _make_llm(partial)
        service = StoryAnalystService(llm, PromptBuilder())
        story = _make_story()
        result = await service.extract_anchors(story)
        assert result.resonance_hamartia == "La culpa callada."
        assert result.resonance_anagnorisis != ""  # fallback con sinopsis

    @pytest.mark.asyncio
    async def test_fallback_never_raises(self):
        """Un response completamente vacío devuelve NarrativeAnchors sin lanzar excepción."""
        llm = _make_llm("")
        service = StoryAnalystService(llm, PromptBuilder())
        result = await service.extract_anchors(_make_story())
        assert isinstance(result, NarrativeAnchors)
        assert result.resonance_hamartia != ""


class TestResolveAnchors:
    """resolve_beat_anchors() implementa mapeo 1:1 Beat N → resonancia N (Spec-081)."""

    def _make_anchors(self) -> NarrativeAnchors:
        return NarrativeAnchors(
            story_id=uuid.uuid4(),
            resonance_hamartia="La grieta del narrador",
            resonance_hybris="La transgresión",
            resonance_anagnorisis="La figura inmóvil en el claro",
            resonance_peripeteia="El espacio como trampa",
            resonance_residual="La mancha permanente",
        )

    def test_beat1_returns_hamartia(self):
        service = StoryAnalystService(MagicMock(), PromptBuilder())
        result = service.resolve_beat_anchors(self._make_anchors(), 1)
        assert result["resonance"] == "La grieta del narrador"

    def test_beat2_returns_hybris(self):
        service = StoryAnalystService(MagicMock(), PromptBuilder())
        result = service.resolve_beat_anchors(self._make_anchors(), 2)
        assert result["resonance"] == "La transgresión"

    def test_beat3_returns_anagnorisis(self):
        service = StoryAnalystService(MagicMock(), PromptBuilder())
        result = service.resolve_beat_anchors(self._make_anchors(), 3)
        assert result["resonance"] == "La figura inmóvil en el claro"

    def test_beat4_returns_peripeteia(self):
        service = StoryAnalystService(MagicMock(), PromptBuilder())
        result = service.resolve_beat_anchors(self._make_anchors(), 4)
        assert result["resonance"] == "El espacio como trampa"

    def test_beat5_returns_residual(self):
        service = StoryAnalystService(MagicMock(), PromptBuilder())
        result = service.resolve_beat_anchors(self._make_anchors(), 5)
        assert result["resonance"] == "La mancha permanente"

    def test_label_voz_is_included(self):
        service = StoryAnalystService(MagicMock(), PromptBuilder())
        result = service.resolve_beat_anchors(self._make_anchors(), 1)
        assert "label_voz" in result
        assert result["label_voz"] != ""

    def test_unknown_beat_returns_empty(self):
        service = StoryAnalystService(MagicMock(), PromptBuilder())
        result = service.resolve_beat_anchors(self._make_anchors(), 99)
        assert result == {}

    def test_all_five_beats_resolve(self):
        service = StoryAnalystService(MagicMock(), PromptBuilder())
        anchors = self._make_anchors()
        for beat_id in range(1, 6):
            result = service.resolve_beat_anchors(anchors, beat_id)
            assert result.get("resonance") != ""
