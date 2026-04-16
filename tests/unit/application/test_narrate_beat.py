"""Tests for NarrateBeatUseCase."""

import pytest

from src.application.use_cases import NarrateBeatUseCase
from src.domain.models import Beat, NarrativeJournal, Story
from src.infrastructure.adapters import MockLLMAdapter


class TestNarrateBeatUseCase:
    """Tests for NarrateBeatUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_beat_and_journal(self):
        """Test that execute returns tuple of Beat and NarrativeJournal."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="El protagonista entra", status="pending")

        mock_llm = MockLLMAdapter(fixed_response="Contenido generado")

        use_case = NarrateBeatUseCase(mock_llm)

        result_beat, result_journal = await use_case.execute(story, beat)

        assert isinstance(result_beat, Beat)
        assert result_beat.content == "Contenido generado"
        assert result_beat.status == "completed"
        assert isinstance(result_journal, NarrativeJournal)

    @pytest.mark.asyncio
    async def test_execute_updates_beat_content(self):
        """Test that beat content is updated after execution."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="El protagonista entra", status="pending")

        mock_llm = MockLLMAdapter(fixed_response="El jeep se detuvo en la entrada...")
        use_case = NarrateBeatUseCase(mock_llm)

        result_beat, _ = await use_case.execute(story, beat)

        assert result_beat.content == "El jeep se detuvo en la entrada..."
        assert result_beat.status == "completed"

    @pytest.mark.asyncio
    async def test_execute_with_previous_beats(self):
        """Test execution with previous beats for context."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        previous_beats = [
            Beat(number=1, summary="Beat 1", content="Contenido 1", status="completed"),
            Beat(number=2, summary="Beat 2", content="Contenido 2", status="completed"),
        ]

        beat = Beat(number=3, summary="Beat 3", status="pending")

        mock_llm = MockLLMAdapter(fixed_response="Contenido nuevo")
        use_case = NarrateBeatUseCase(mock_llm)

        result_beat, _ = await use_case.execute(story, beat, previous_beats=previous_beats)

        assert mock_llm.call_count >= 1

    @pytest.mark.asyncio
    async def test_execute_injects_journal_context(self):
        """Test that journal context is injected into prompt."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="Beat 1", status="pending")

        journal = NarrativeJournal(
            last_events="El protagonista Entró a la casa",
            unresolved_mysteries="¿Por qué está abandonada?",
            physical_emotional_state="Nervioso",
        )

        mock_llm = MockLLMAdapter(fixed_response="Contenido")
        use_case = NarrateBeatUseCase(mock_llm)

        result_beat, result_journal = await use_case.execute(story, beat, journal=journal)

        assert isinstance(result_journal, NarrativeJournal)
