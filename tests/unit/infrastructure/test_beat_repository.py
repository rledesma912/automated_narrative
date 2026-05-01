"""Tests for SQLBeatRepository."""

import os
import tempfile
from uuid import uuid4

import pytest

from src.config import settings
from src.domain.models import Beat, Story
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository


class TestSqlBeatRepository:
    """Tests for SQLBeatRepository."""

    @pytest.fixture
    def temp_db_path(self, monkeypatch):
        """Create temporary database path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{path}")
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    async def setup_db(self, temp_db_path):
        """Initialize database."""
        await init_db()

    @pytest.fixture
    def repo(self):
        """Create repository instance."""
        return SQLBeatRepository()

    @pytest.fixture
    def story_id(self):
        """Create a story ID."""
        return uuid4()

    @pytest.fixture
    async def saved_story_id(self, setup_db, story_id):
        """Inserta una story padre en la DB para satisfacer la FK de macro_beat."""
        story = Story(
            id=story_id,
            title="Story para test",
            protagonista="Test",
            relator="tercera_persona",
            sinopsis="Sinopsis de test",
            atmosfera="terror",
        )
        await SQLStoryRepository().save(story)
        return story_id

    @pytest.mark.asyncio
    async def test_save_beat(self, repo, saved_story_id):
        """Test saving a beat to database."""
        beat = Beat(number=1, summary="Beat summary")

        result = await repo.save(beat, saved_story_id)

        assert result.number == 1
        assert result.summary == "Beat summary"

    @pytest.mark.asyncio
    async def test_get_by_story(self, repo, saved_story_id):
        """Test retrieving beats by story ID."""
        beat1 = Beat(number=1, summary="First beat")
        beat2 = Beat(number=2, summary="Second beat")

        await repo.save(beat1, saved_story_id)
        await repo.save(beat2, saved_story_id)

        results = await repo.get_by_story(saved_story_id)

        assert len(results) == 2
        assert results[0].number == 1
        assert results[1].number == 2

    @pytest.mark.asyncio
    async def test_get_by_number(self, repo, saved_story_id):
        """Test retrieving a specific beat by number."""
        beat = Beat(number=3, summary="Third beat")

        await repo.save(beat, saved_story_id)
        result = await repo.get_by_number(saved_story_id, 3)

        assert result is not None
        assert result.number == 3
        assert result.summary == "Third beat"

    @pytest.mark.asyncio
    async def test_get_by_number_returns_none(self, repo, saved_story_id):
        """Test that get_by_number returns None for nonexistent."""
        result = await repo.get_by_number(saved_story_id, 999)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_beat(self, repo, saved_story_id):
        """Test updating a beat."""
        beat = Beat(number=1, summary="Original", status="pending")

        await repo.save(beat, saved_story_id)

        beat.content = "Updated content"
        beat.status = "completed"
        result = await repo.update(beat, saved_story_id)

        assert result.content == "Updated content"
        assert result.status == "completed"
