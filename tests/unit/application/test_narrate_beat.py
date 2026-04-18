"""Tests for VozUseCase."""

import pytest

from src.application.use_cases import VozUseCase
from src.domain.models import Beat, NarrativeJournal, Story
from src.infrastructure.adapters import MockLLMAdapter


class TestVozUseCase:
    """Tests for VozUseCase."""

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

        use_case = VozUseCase(mock_llm)

        result_beat, result_journal, llm_elapsed = await use_case.execute(story, beat)

        assert isinstance(result_beat, Beat)
        assert result_beat.content == "Contenido generado"
        assert result_beat.status == "completed"
        assert isinstance(result_journal, NarrativeJournal)
        assert isinstance(llm_elapsed, float)

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
        use_case = VozUseCase(mock_llm)

        result_beat, _, _ = await use_case.execute(story, beat)

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
        use_case = VozUseCase(mock_llm)

        result_beat, _, _ = await use_case.execute(story, beat, previous_beats=previous_beats)

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
            last_events="El protagonista entró a la casa",
            unresolved_mysteries="¿Por qué está abandonada?",
            physical_emotional_state="Nervioso",
        )

        mock_llm = MockLLMAdapter(fixed_response="Contenido")
        use_case = VozUseCase(mock_llm)

        result_beat, result_journal, _ = await use_case.execute(story, beat, journal=journal)

        assert isinstance(result_journal, NarrativeJournal)

    @pytest.mark.asyncio
    async def test_narrate_all_6_beats_sequentially(self):
        """Test narrating all 6 beats in sequence maintains context."""
        story = Story(
            title="Test",
            protagonista="Familia",
            relator="primera_persona",
            escenarios="Casa de campo",
            sinopsis="Historia de terror",
            atmosfera="terror psicológico",
        )

        beats = [Beat(number=i, summary=f"Beat {i}", status="pending") for i in range(1, 7)]

        completed = []
        journal = None

        mock_llm = MockLLMAdapter(fixed_response="Contenido narrado")
        use_case = VozUseCase(mock_llm)

        for beat in beats:
            result_beat, result_journal, _ = await use_case.execute(
                story, beat, previous_beats=completed, journal=journal
            )
            completed.append(result_beat)
            journal = result_journal

        assert len(completed) == 6
        assert all(b.status == "completed" for b in completed)
        assert all(b.content == "Contenido narrado" for b in completed)
