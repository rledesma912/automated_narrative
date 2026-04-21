"""Tests para SQLNarrativeAnchorsRepository (Spec-038)."""

import os
import tempfile
import uuid

import pytest

from src.config import settings
from src.domain.models import NarrativeAnchors
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLNarrativeAnchorsRepository


class TestSqlNarrativeAnchorsRepository:

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
        return SQLNarrativeAnchorsRepository()

    @pytest.fixture
    def story_id(self):
        return uuid.uuid4()

    def _make_anchors(self, story_id):
        return NarrativeAnchors(
            story_id=story_id,
            initial_state="Irene llega tranquila al campo.",
            threat_nature="Una presencia que imita a los conocidos.",
            horror_peak="La figura de María inmóvil en el claro del monte.",
            spatial_anchor="Monte de los Espinillos: espinillos cerrados, barro, relámpagos.",
        )

    @pytest.mark.asyncio
    async def test_save_and_get(self, repo, setup_db, story_id):
        anchors = self._make_anchors(story_id)
        await repo.save(anchors)
        result = await repo.get_by_story(story_id)
        assert result is not None
        assert result.initial_state == anchors.initial_state
        assert result.threat_nature == anchors.threat_nature
        assert result.horror_peak == anchors.horror_peak
        assert result.spatial_anchor == anchors.spatial_anchor

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, repo, setup_db):
        result = await repo.get_by_story(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_save_replaces_existing(self, repo, setup_db, story_id):
        anchors = self._make_anchors(story_id)
        await repo.save(anchors)
        updated = anchors.model_copy(update={"initial_state": "Estado actualizado."})
        await repo.save(updated)
        result = await repo.get_by_story(story_id)
        assert result.initial_state == "Estado actualizado."
