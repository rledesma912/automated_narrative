"""Tests for MemoryJournalist service."""

import pytest

from src.application.services import MemoryJournalist
from src.domain.models import Beat, NarrativeJournal, Story
from src.infrastructure.adapters import MockLLMAdapter


class TestMemoryJournalist:
    """Tests for MemoryJournalist service."""

    @pytest.mark.asyncio
    async def test_update_journal_returns_journal(self):
        """Test that update_journal returns a NarrativeJournal."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="El protagonista entra", content="Contenido de prueba")

        mock_llm = MockLLMAdapter(
            fixed_response='{"last_events": "Entraron a la casa", "unresolved_mysteries": "", "physical_emotional_state": "Nervioso"}'
        )

        journalist = MemoryJournalist(mock_llm)
        journal = await journalist.update_journal(story, beat)

        assert isinstance(journal, NarrativeJournal)
        assert journal.last_events == "Entraron a la casa"

    @pytest.mark.asyncio
    async def test_summarize_beats_empty(self):
        """Test summarizing empty beats."""
        mock_llm = MockLLMAdapter()
        journalist = MemoryJournalist(mock_llm)

        result = await journalist.summarize_beats([])

        assert result == ""

    @pytest.mark.asyncio
    async def test_summarize_beats_with_content(self):
        """Test summarizing beats with content."""
        from src.domain.models import Beat

        beats = [
            Beat(number=1, summary="Beat 1", content="Contenido 1", status="completed"),
            Beat(number=2, summary="Beat 2", content="Contenido 2", status="completed"),
            Beat(number=3, summary="Beat 3", content="Contenido 3", status="completed"),
        ]

        mock_llm = MockLLMAdapter()
        journalist = MemoryJournalist(mock_llm)

        result = await journalist.summarize_beats(beats)

        assert "Beat 1" in result
        assert "Beat 2" in result
        assert "Beat 3" in result

    @pytest.mark.asyncio
    async def test_summarize_beats_limits_to_3(self):
        """Test that summarize_beats limits to last 3 beats."""
        beats = [
            Beat(number=1, summary="Beat 1", content="C1", status="completed"),
            Beat(number=2, summary="Beat 2", content="C2", status="completed"),
            Beat(number=3, summary="Beat 3", content="C3", status="completed"),
            Beat(number=4, summary="Beat 4", content="C4", status="completed"),
            Beat(number=5, summary="Beat 5", content="C5", status="completed"),
        ]

        mock_llm = MockLLMAdapter()
        journalist = MemoryJournalist(mock_llm)

        result = await journalist.summarize_beats(beats)

        assert "Beat 3" in result
        assert "Beat 4" in result
        assert "Beat 5" in result
        assert "2 beats anteriores" in result
