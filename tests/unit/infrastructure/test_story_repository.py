"""Tests for SQLStoryRepository."""

import os
import tempfile

import pytest

from src.config import settings
from src.domain.models import Story, StoryStatus
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLStoryRepository


class TestSqlStoryRepository:
    """Tests for SQLStoryRepository."""

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
        return SQLStoryRepository()

    @pytest.mark.asyncio
    async def test_save_story(self, repo, setup_db, temp_db_path):
        """Test saving a story to database."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        result = await repo.save(story)

        assert result.id == story.id
        assert result.title == "Test Story"

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, setup_db, temp_db_path):
        """Test retrieving a story by ID."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        await repo.save(story)
        result = await repo.get_by_id(story.id)

        assert result is not None
        assert result.id == story.id
        assert result.title == "Test Story"

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_nonexistent(self, repo, setup_db, temp_db_path):
        """Test that get_by_id returns None for nonexistent ID."""
        from uuid import uuid4

        fake_id = uuid4()
        result = await repo.get_by_id(fake_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_story(self, repo, setup_db, temp_db_path):
        """Test updating a story."""
        story = Story(
            title="Original Title",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        await repo.save(story)

        story.title = "Updated Title"
        story.status = StoryStatus.COMPLETED
        result = await repo.update(story)

        assert result.title == "Updated Title"
        assert result.status == StoryStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_list_all(self, repo, setup_db, temp_db_path):
        """Test listing all stories."""
        story1 = Story(
            title="Story 1",
            protagonista="P1",
            relator="primera",
            escenarios="E1",
            sinopsis="S1",
            atmosfera="terror",
        )
        story2 = Story(
            title="Story 2",
            protagonista="P2",
            relator="primera",
            escenarios="E2",
            sinopsis="S2",
            atmosfera="horror",
        )

        await repo.save(story1)
        await repo.save(story2)

        results = await repo.list_all()

        assert len(results) == 2
        titles = {r.title for r in results}
        assert "Story 1" in titles
        assert "Story 2" in titles
