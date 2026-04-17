"""Tests for DirectorUseCase."""

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases import DirectorUseCase
from src.domain.models import Story, StoryPlan
from src.infrastructure.adapters import MockLLMAdapter


class TestDirectorUseCase:
    """Tests for DirectorUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_story_plan(self):
        """Test that execute returns a StoryPlan."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(fixed_response="1. Beat one\n2. Beat two\n3. Beat three")

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story, num_beats=3)

        assert isinstance(result, StoryPlan)
        assert result.title == "Test Story"
        assert result.story_id == story.id

    @pytest.mark.asyncio
    async def test_execute_parses_beats_from_response(self):
        """Test that beats are parsed from LLM response."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(fixed_response="1. Primer beat\n2. Segundo beat\n3. Tercer beat")

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story, num_beats=3)

        assert len(result.beats) == 3
        assert result.beats[0].number == 1
        assert "Primer" in result.beats[0].summary

    @pytest.mark.asyncio
    async def test_execute_returns_default_beats_on_parse_failure(self):
        """Test that default beats are returned when parsing fails."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(fixed_response="")

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story, num_beats=8)

        assert len(result.beats) == 8
        assert result.beats[0].status == "pending"

    @pytest.mark.asyncio
    async def test_generate_6_narrative_beats(self):
        """Test generating 6 narrative beats (Apertura, Incidente, Subida, Crisis, Cumbre, Desenlace)."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(
            fixed_response="""1. Apertura: La familia llega a la casa
2. Incidente: El caballo se empaca en la tormenta
3. Subida: Primeras sombras en el bosque
4. Crisis: Apariciones en el camino
5. Cumbre: Todo parece perdido
6. Desenlace: La oración los salva"""
        )

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story, num_beats=6)

        assert len(result.beats) == 6
        assert result.beats[0].summary.startswith("Apertura")
        assert result.beats[1].summary.startswith("Incidente")
        assert result.beats[2].summary.startswith("Subida")
        assert result.beats[3].summary.startswith("Crisis")
        assert result.beats[4].summary.startswith("Cumbre")
        assert result.beats[5].summary.startswith("Desenlace")

    def test_parse_beats_formats_correctly(self):
        """Test _parse_beats parses different formats."""
        story = Story(
            title="Test",
            protagonista="X",
            relator="tercera",
            escenarios="Y",
            sinopsis="Z",
            atmosfera="terror",
        )

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(MockLLMAdapter(), prompt_builder)

        beats = use_case._parse_beats("1. First beat\n2. Second beat\n3. Third beat", story.id, 3)

        assert len(beats) == 3
        assert beats[0].summary == "First beat"
        assert beats[1].summary == "Second beat"
        assert beats[2].summary == "Third beat"
