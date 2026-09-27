"""Tests para use cases de lectura y actualización — Spec-060 Issues 7 y 8."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.use_cases.get_story import GetStoryByIdUseCase
from src.application.use_cases.list_beats import ListBeatsUseCase
from src.application.use_cases.list_stories import ListStoriesUseCase
from src.domain.models import Beat, Story


def _story(title: str = "T") -> Story:
    return Story(
        title=title, protagonista="P", relator="tercera_persona", sinopsis="S", atmosfera="a"
    )


def _beat(number: int = 1, summary: str = "evento") -> Beat:
    return Beat(number=number, generated_act=summary, status="pending")


class TestListStoriesUseCase:
    @pytest.mark.asyncio
    async def test_execute_delega_a_repo(self):
        repo = MagicMock()
        repo.list_all = AsyncMock(return_value=[_story("A"), _story("B")])
        use_case = ListStoriesUseCase(repo)
        result = await use_case.execute()
        repo.list_all.assert_called_once()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_execute_retorna_lista_vacia(self):
        repo = MagicMock()
        repo.list_all = AsyncMock(return_value=[])
        result = await ListStoriesUseCase(repo).execute()
        assert result == []


class TestGetStoryByIdUseCase:
    @pytest.mark.asyncio
    async def test_execute_retorna_historia(self):
        story = _story("X")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=story)
        sid = uuid.uuid4()
        result = await GetStoryByIdUseCase(repo).execute(sid)
        repo.get_by_id.assert_called_once_with(sid)
        assert result is story

    @pytest.mark.asyncio
    async def test_execute_retorna_none_si_no_existe(self):
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=None)
        result = await GetStoryByIdUseCase(repo).execute(uuid.uuid4())
        assert result is None


class TestListBeatsUseCase:
    @pytest.mark.asyncio
    async def test_execute_delega_a_repo(self):
        beats = [_beat(1), _beat(2)]
        repo = MagicMock()
        repo.get_by_story = AsyncMock(return_value=beats)
        sid = uuid.uuid4()
        result = await ListBeatsUseCase(repo).execute(sid)
        repo.get_by_story.assert_called_once_with(sid)
        assert result == beats

    @pytest.mark.asyncio
    async def test_execute_retorna_lista_vacia(self):
        repo = MagicMock()
        repo.get_by_story = AsyncMock(return_value=[])
        result = await ListBeatsUseCase(repo).execute(uuid.uuid4())
        assert result == []


class TestCreateStoryUseCaseErrorPaths:
    @pytest.mark.asyncio
    async def test_create_story_db_failure_propagates(self):
        """Repositorio lanza excepción en save() — el use case la propaga al caller."""
        from src.application.dto import StoryCreateDTO
        from src.application.use_cases.create_story import CreateStoryUseCase

        repo = MagicMock()
        repo.save = AsyncMock(side_effect=RuntimeError("DB connection lost"))

        dto = StoryCreateDTO(
            title="T",
            protagonista="P",
            relator="tercera_persona",
            sinopsis="S",
            atmosfera="terror",
        )

        with pytest.raises(RuntimeError, match="DB connection lost"):
            await CreateStoryUseCase(repo).execute(dto)
