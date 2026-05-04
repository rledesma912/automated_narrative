"""Tests for StoryRunner orchestrator."""

import tempfile
from pathlib import Path

import pytest

from src.application.services import PromptBuilder
from src.config import settings
from src.core.orchestrator import StoryRunner
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository


class TestStoryRunner:
    """Tests for StoryRunner."""

    @pytest.fixture
    def temp_db_path(self, monkeypatch):
        """Create temporary database."""
        fd, path = tempfile.mkstemp(suffix=".db")
        import os

        os.close(fd)
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{path}")
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    async def setup_db(self, temp_db_path):
        """Initialize database."""
        await init_db()

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM adapter."""
        return MockLLMAdapter(fixed_response="Beat narrado")

    @pytest.fixture
    def story_repo(self):
        """Create story repository."""
        return SQLStoryRepository()

    @pytest.fixture
    def beat_repo(self):
        """Create beat repository."""
        return SQLBeatRepository()

    @pytest.fixture
    def prompt_builder(self):
        """Create prompt builder."""
        return PromptBuilder()

    @pytest.mark.asyncio
    async def test_orchestrator_run_full_creates_story(
        self, setup_db, temp_output_dir, mock_llm, story_repo, beat_repo, prompt_builder
    ):
        """Test that run_full creates a story."""
        runner = StoryRunner(
            llm_adapter=mock_llm,
            story_repo=story_repo,
            beat_repo=beat_repo,
            prompt_builder=prompt_builder,
            output_dir=temp_output_dir,
        )

        story = await runner.run_full(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        assert story is not None
        assert story.title == "Test Story"

    @pytest.mark.asyncio
    async def test_orchestrator_saves_beats(
        self, setup_db, temp_output_dir, mock_llm, story_repo, beat_repo, prompt_builder
    ):
        """Test that orchestrator saves beats to DB."""
        runner = StoryRunner(
            llm_adapter=mock_llm,
            story_repo=story_repo,
            beat_repo=beat_repo,
            prompt_builder=prompt_builder,
            output_dir=temp_output_dir,
        )

        story = await runner.run_full(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beats = await beat_repo.get_by_story(story.id)
        assert len(beats) >= 3

    @pytest.mark.asyncio
    async def test_orchestrator_narrates_beats(
        self, setup_db, temp_output_dir, mock_llm, story_repo, beat_repo, prompt_builder
    ):
        """Test that orchestrator narrates beats."""
        runner = StoryRunner(
            llm_adapter=mock_llm,
            story_repo=story_repo,
            beat_repo=beat_repo,
            prompt_builder=prompt_builder,
            output_dir=temp_output_dir,
        )

        story = await runner.run_full(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beats = await beat_repo.get_by_story(story.id)
        completed_beats = [b for b in beats if b.status == "completed"]
        assert len(completed_beats) > 0
        assert any(b.content != "" for b in completed_beats)
