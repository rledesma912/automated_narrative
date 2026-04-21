"""Tests para SQLScenarioRepository (Spec-038)."""

import os
import tempfile
import uuid

import pytest

from src.config import settings
from src.domain.models import Scenario
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLScenarioRepository


class TestSqlScenarioRepository:

    @pytest.fixture
    def temp_db_path(self, monkeypatch):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{path}")
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    async def setup_db(self, temp_db_path):
        await init_db()

    @pytest.fixture
    def repo(self):
        return SQLScenarioRepository()

    @pytest.fixture
    def story_id(self):
        return uuid.uuid4()

    def _make_scenarios(self, story_id):
        return [
            Scenario(story_id=story_id, order_index=1, name="La casa de la abuela"),
            Scenario(story_id=story_id, order_index=2, name="La estancia de la fiesta"),
            Scenario(story_id=story_id, order_index=3, name="Monte de los Espinillos"),
        ]

    @pytest.mark.asyncio
    async def test_save_batch_and_get_by_story(self, repo, setup_db, story_id):
        scenarios = self._make_scenarios(story_id)
        await repo.save_batch(scenarios, story_id)
        result = await repo.get_by_story(story_id)
        assert len(result) == 3
        assert result[0].name == "La casa de la abuela"
        assert result[2].name == "Monte de los Espinillos"

    @pytest.mark.asyncio
    async def test_get_by_story_preserves_order(self, repo, setup_db, story_id):
        scenarios = self._make_scenarios(story_id)
        await repo.save_batch(scenarios, story_id)
        result = await repo.get_by_story(story_id)
        assert [s.order_index for s in result] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_by_story_empty(self, repo, setup_db, story_id):
        result = await repo.get_by_story(story_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_by_story(self, repo, setup_db, story_id):
        scenarios = self._make_scenarios(story_id)
        await repo.save_batch(scenarios, story_id)
        await repo.delete_by_story(story_id)
        result = await repo.get_by_story(story_id)
        assert result == []
