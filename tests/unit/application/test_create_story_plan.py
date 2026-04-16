"""Tests for CreateStoryPlanUseCase."""

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases import CreateStoryPlanUseCase
from src.domain.models import Story, StoryPlan
from src.infrastructure.adapters import MockLLMAdapter


class TestCreateStoryPlanUseCase:
    """Tests for CreateStoryPlanUseCase."""

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
        use_case = CreateStoryPlanUseCase(mock_llm, prompt_builder)

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
        use_case = CreateStoryPlanUseCase(mock_llm, prompt_builder)

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
        use_case = CreateStoryPlanUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story, num_beats=8)

        assert len(result.beats) == 8
        assert result.beats[0].status == "pending"
