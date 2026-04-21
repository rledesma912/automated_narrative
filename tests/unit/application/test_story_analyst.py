"""Tests del expansor de sinopsis (Spec 023)."""

from unittest.mock import patch

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases.director_use_case import DirectorUseCase
from src.domain.models import Story
from src.infrastructure.adapters import MockLLMAdapter


def _make_story(**kwargs):
    defaults = dict(
        title="El Monte",
        protagonista="Irene",
        relator="primera_persona",
        escenarios="Monte de los Espinillos",
        sinopsis="Una familia sube al monte y encuentra señales extrañas.",
        atmosfera="terror folclórico",
    )
    defaults.update(kwargs)
    return Story(**defaults)


class TestExpandSynopsis:

    @pytest.mark.asyncio
    async def test_analyze_story_returns_string(self):
        """_analyze_story() retorna el texto normalizado del LLM."""
        brief_text = "Amenaza: entidad del monte. Estado inicial: confiada."
        llm = MockLLMAdapter(fixed_response=brief_text)
        director = DirectorUseCase(llm, PromptBuilder())
        story = _make_story()
        result = await director._analyze_story(story)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_analyze_story_sets_story_narrative_brief(self):
        """_analyze_story() muta story.narrative_brief con el resultado."""
        brief_text = "Amenaza: entidad del monte."
        llm = MockLLMAdapter(fixed_response=brief_text)
        director = DirectorUseCase(llm, PromptBuilder())
        story = _make_story()
        assert story.narrative_brief == ""
        await director._analyze_story(story)
        assert story.narrative_brief == brief_text

    @pytest.mark.asyncio
    async def test_execute_calls_llm_twice(self):
        """execute() hace 2 llamadas LLM: expansor primero, mapper después."""
        llm = MockLLMAdapter(fixed_response="1. Beat uno\n2. Beat dos\n3. Beat tres\n4. Beat cuatro\n5. Beat cinco")
        director = DirectorUseCase(llm, PromptBuilder())
        await director.execute(_make_story())
        assert llm.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_passes_brief_to_mapper(self):
        """El brief de _analyze_story llega a build_synopsis_mapper_prompt."""
        from unittest.mock import AsyncMock

        expected_brief = "Amenaza: la entidad del monte que acecha."
        llm = MockLLMAdapter(fixed_response="1. A\n2. B\n3. C\n4. D\n5. E")
        builder = PromptBuilder()

        received_briefs = []
        original = builder.build_synopsis_mapper_prompt

        def capture(story, narrative_brief=""):
            received_briefs.append(narrative_brief)
            return original(story, narrative_brief)

        director = DirectorUseCase(llm, builder)
        with patch.object(director, "_analyze_story", new=AsyncMock(return_value=expected_brief)):
            with patch.object(builder, "build_synopsis_mapper_prompt", side_effect=capture):
                await director.execute(_make_story())

        assert received_briefs[0] == expected_brief

    @pytest.mark.asyncio
    async def test_story_analyst_uses_story_analyst_role(self):
        """El expansor llama al LLM con role='story_analyst'."""
        roles_used = []

        class RoleCaptureLLM(MockLLMAdapter):
            async def generate(self, prompt, role=None, **kwargs):
                roles_used.append(role)
                return await super().generate(prompt, role=role, **kwargs)

        llm = RoleCaptureLLM(fixed_response="1. A\n2. B\n3. C\n4. D\n5. E")
        director = DirectorUseCase(llm, PromptBuilder())
        await director.execute(_make_story())

        assert roles_used[0] == "story_analyst"
        assert roles_used[1] == "director"

    @pytest.mark.asyncio
    async def test_build_story_analyst_prompt_compact(self):
        """build_story_analyst_prompt() carga story_analyst_compact.md con perfil compact."""
        builder = PromptBuilder()
        story = _make_story()
        with patch.object(builder, "_get_prompt_variant", return_value="compact"):
            prompt = builder.build_story_analyst_prompt(story)
        assert "SINOPSIS" in prompt or "sinopsis" in prompt.lower()
        assert story.sinopsis in prompt

    @pytest.mark.asyncio
    async def test_build_story_analyst_prompt_frontier(self):
        """build_story_analyst_prompt() carga story_analyst.md con perfil frontier."""
        builder = PromptBuilder()
        story = _make_story()
        with patch.object(builder, "_get_prompt_variant", return_value="frontier"):
            prompt = builder.build_story_analyst_prompt(story)
        assert story.sinopsis in prompt

    @pytest.mark.asyncio
    async def test_debug_collector_records_story_analyst_call(self):
        """El DebugCollector registra la llamada del expansor con role='story_analyst'."""
        from src.application.services.debug_collector import DebugCollector

        llm = MockLLMAdapter(fixed_response="1. A\n2. B\n3. C\n4. D\n5. E")
        collector = DebugCollector(active=True)
        director = DirectorUseCase(llm, PromptBuilder(), debug_collector=collector)
        await director.execute(_make_story())

        story_analyst_records = [r for r in collector.records if r.role == "story_analyst"]
        assert len(story_analyst_records) == 1
        assert story_analyst_records[0].beat_number is None
        assert story_analyst_records[0].parser_result == "n/a"
