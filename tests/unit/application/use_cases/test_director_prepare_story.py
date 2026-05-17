"""Tests para DirectorUseCase.prepare_story (Spec-500 S-B)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.use_cases.director_use_case import DirectorUseCase


class TestPrepareStory:
    @pytest.fixture
    def mock_services(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=MagicMock(text="analyst response", elapsed_s=0.5))
        pb = MagicMock()
        pb.num_beats = 5
        pb.get_variant_name.return_value = "compact"
        return llm, pb

    @pytest.mark.asyncio
    async def test_prepare_story_returns_three_values(self, mock_services):
        llm, pb = mock_services

        director = DirectorUseCase(llm=llm, prompt_builder=pb)

        with patch(
            "src.application.services.story_analyst_service.StoryAnalystService.extract_anchors",
            new_callable=AsyncMock,
            return_value={"hamartia": "anchor1"},
        ):
            with patch(
                "src.application.services.scenario_resolver_service.ScenarioResolverService.resolve_distribution",
                new_callable=AsyncMock,
                return_value={"1": {"scenario_id": "S1"}},
            ):
                anchors, distribution, num_beats = await director.prepare_story(MagicMock())

        assert isinstance(anchors, dict)
        assert isinstance(distribution, dict)
        assert num_beats == 5

    @pytest.mark.asyncio
    async def test_prepare_story_calls_story_analyst(self, mock_services):
        llm, pb = mock_services
        mock_story = MagicMock()
        mock_story.id = "test-id"

        with patch(
            "src.application.services.story_analyst_service.StoryAnalystService.extract_anchors",
            new_callable=AsyncMock,
            return_value={"key": "value"},
        ) as mock_extract:
            director = DirectorUseCase(llm=llm, prompt_builder=pb)
            await director.prepare_story(mock_story)
            mock_extract.assert_called_once_with(mock_story)

    @pytest.mark.asyncio
    async def test_prepare_story_calls_resolver(self, mock_services):
        llm, pb = mock_services
        mock_story = MagicMock()

        with patch(
            "src.application.services.story_analyst_service.StoryAnalystService.extract_anchors",
            new_callable=AsyncMock,
            return_value={"anchor": "val"},
        ):
            with patch(
                "src.application.services.scenario_resolver_service.ScenarioResolverService.resolve_distribution",
                new_callable=AsyncMock,
                return_value={"1": {"scenario_id": "S1"}},
            ) as mock_resolve:
                director = DirectorUseCase(llm=llm, prompt_builder=pb)
                await director.prepare_story(mock_story)
                mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_prepare_story_calls_callbacks(self, mock_services):
        llm, pb = mock_services
        mock_story = MagicMock()

        cb_analyst = MagicMock()
        cb_resolver = MagicMock()

        with patch(
            "src.application.services.story_analyst_service.StoryAnalystService.extract_anchors",
            new_callable=AsyncMock,
            return_value={},
        ):
            with patch(
                "src.application.services.scenario_resolver_service.ScenarioResolverService.resolve_distribution",
                new_callable=AsyncMock,
                return_value={},
            ):
                director = DirectorUseCase(llm=llm, prompt_builder=pb)
                await director.prepare_story(
                    mock_story,
                    on_analyst_done=cb_analyst,
                    on_resolver_done=cb_resolver,
                )
                cb_analyst.assert_called()
                cb_resolver.assert_called()

    @pytest.mark.asyncio
    async def test_prepare_story_returns_num_beats_from_prompt_builder(self, mock_services):
        llm, pb = mock_services
        pb.num_beats = 8
        mock_story = MagicMock()

        with patch(
            "src.application.services.story_analyst_service.StoryAnalystService.extract_anchors",
            new_callable=AsyncMock,
            return_value={},
        ):
            with patch(
                "src.application.services.scenario_resolver_service.ScenarioResolverService.resolve_distribution",
                new_callable=AsyncMock,
                return_value={},
            ):
                director = DirectorUseCase(llm=llm, prompt_builder=pb)
                _, _, num = await director.prepare_story(mock_story)
                assert num == 8
