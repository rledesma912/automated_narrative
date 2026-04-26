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
