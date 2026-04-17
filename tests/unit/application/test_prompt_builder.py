"""Tests for PromptBuilder service."""

from src.application.services import PromptBuilder
from src.domain.models import Story


class TestPromptBuilder:
    """Tests for PromptBuilder service."""

    def test_build_system_prompt(self):
        """Test building system prompt."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
            reglas=["Sin miedo"],
        )

        builder = PromptBuilder()
        prompt = builder.build_system_prompt(story)

        assert "terror" in prompt
        assert "tercera_persona" in prompt
        assert "Protagonist" in prompt

    def test_build_planner_prompt(self):
        """Test building planner prompt."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Casa embrujada",
            sinopsis="Una historia de terror",
            atmosfera="horror",
        )

        builder = PromptBuilder()
        prompt = builder.build_planner_prompt(story, num_beats=5)

        assert "Test Story" in prompt
        assert "5" in prompt
        assert "Casa embrujada" in prompt

    def test_build_beat_prompt(self):
        """Test building beat prompt."""
        from src.domain.models import Beat

        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="El protagonista entra a la casa")

        builder = PromptBuilder()
        prompt = builder.build_beat_prompt(story, beat)

        assert "BEAT #1" in prompt
        assert "El protagonista entra a la casa" in prompt

    def test_build_beat_prompt_with_previous_context(self):
        """Test building beat prompt with previous beats."""
        from src.domain.models import Beat

        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat1 = Beat(
            number=1, summary="El protagonista llega a la puerta", content="Llegó a la puerta."
        )
        beat2 = Beat(number=2, summary="El protagonista sube las escaleras")

        builder = PromptBuilder()
        prompt = builder.build_beat_prompt(story, beat2, previous_beats=[beat1], total_beats=5)

        assert "BEAT #2" in prompt or "beat #2" in prompt.lower()

    def test_build_beat_prompt_with_relator_name(self):
        """Test beat prompt includes specific relator name."""
        from src.domain.models import Beat

        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="Irene",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="Llegan a la casa")

        builder = PromptBuilder()
        prompt = builder.build_beat_prompt(story, beat, total_beats=10)

        assert "Irene" in prompt
        assert "primera persona" in prompt.lower()

    def test_build_voice_prompt(self):
        """Test building voice prompt."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror_psicologico",
        )

        builder = PromptBuilder()
        prompt = builder.build_voice_prompt(story)

        assert "terror_psicologico" in prompt
        assert "primera_persona" in prompt
