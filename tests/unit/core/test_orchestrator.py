"""Tests for StoryRunner orchestrator."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.config import settings
from src.core.orchestrator import StoryRunner
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import (
    SQLBeatRepository,
    SQLGeneratedNarrativeRepository,
    SQLStoryRepository,
)


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
            "Test Story",
            "Protagonist",
            "tercera_persona",
            [],
            "Synopsis",
            "terror",
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
            "Test Story",
            "Protagonist",
            "tercera_persona",
            [],
            "Synopsis",
            "terror",
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
            "Test Story",
            "Protagonist",
            "tercera_persona",
            [],
            "Synopsis",
            "terror",
        )

        beats = await beat_repo.get_by_story(story.id)
        completed_beats = [b for b in beats if b.status == "completed"]
        assert len(completed_beats) > 0
        assert any(b.generated_act != "" for b in completed_beats)

    # ── Spec-312: persistencia automática de generated_narrative ──────────────

    @pytest.mark.asyncio
    async def test_run_full_persists_generated_narrative_at_end(
        self, setup_db, temp_output_dir, mock_llm, story_repo, beat_repo, prompt_builder
    ):
        """run_full debe crear una fila en generated_narrative al finalizar."""
        narrative_uc = GenerateNarrativesUseCase()
        runner = StoryRunner(
            llm_adapter=mock_llm,
            story_repo=story_repo,
            beat_repo=beat_repo,
            prompt_builder=prompt_builder,
            output_dir=temp_output_dir,
            narrative_use_case=narrative_uc,
        )

        story = await runner.run_full(
            "Spec312 Story",
            "Protagonist",
            "tercera_persona",
            [],
            "Synopsis",
            "terror",
        )

        narratives = await SQLGeneratedNarrativeRepository().get_by_story_template_id(story.id)
        assert len(narratives) == 1
        assert narratives[0].content
        assert narratives[0].title.startswith("Spec312 Story · ")
        assert runner.last_narrative_id == str(narratives[0].id)

    @pytest.mark.asyncio
    async def test_run_full_skips_narrative_when_stop_after_set(
        self, setup_db, temp_output_dir, mock_llm, story_repo, beat_repo, prompt_builder
    ):
        """Con stop_after activo, el pipeline parcial no debe crear generated_narrative."""
        narrative_uc = GenerateNarrativesUseCase()
        runner = StoryRunner(
            llm_adapter=mock_llm,
            story_repo=story_repo,
            beat_repo=beat_repo,
            prompt_builder=prompt_builder,
            output_dir=temp_output_dir,
            narrative_use_case=narrative_uc,
        )

        story = await runner.run_full(
            "Spec312 Stop",
            "Protagonist",
            "tercera_persona",
            [],
            "Synopsis",
            "terror",
            stop_after="analyst",
        )

        narratives = await SQLGeneratedNarrativeRepository().get_by_story_template_id(story.id)
        assert narratives == []
        assert runner.last_narrative_id is None

    @pytest.mark.asyncio
    async def test_run_full_does_not_fail_if_narrative_save_raises(
        self, setup_db, temp_output_dir, mock_llm, story_repo, beat_repo, prompt_builder
    ):
        """Un fallo en la consolidación no debe abortar la generación de la historia."""
        broken_uc = GenerateNarrativesUseCase()
        broken_uc.consolidate_and_save = AsyncMock(side_effect=RuntimeError("boom"))

        runner = StoryRunner(
            llm_adapter=mock_llm,
            story_repo=story_repo,
            beat_repo=beat_repo,
            prompt_builder=prompt_builder,
            output_dir=temp_output_dir,
            narrative_use_case=broken_uc,
        )

        story = await runner.run_full(
            "Spec312 Robusto",
            "Protagonist",
            "tercera_persona",
            [],
            "Synopsis",
            "terror",
        )

        assert story is not None
        assert runner.last_narrative_id is None
        broken_uc.consolidate_and_save.assert_awaited_once()
