"""Tests para stream_story (Spec-201 + Spec-312)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.streaming_service import stream_story
from src.domain.models import (
    BeatStatus,
    BeatType,
    GeneratedNarrative,
    MacroBeat,
    Story,
    StoryStatus,
)
from src.domain.streaming import StreamEventType


def _make_beat(n: int) -> MacroBeat:
    return MacroBeat(
        number=n,
        summary=f"sum {n}",
        generated_act=f"prosa {n}",
        status=BeatStatus.COMPLETED,
        beat_type=BeatType.EXPOSICION,
    )


def _make_story() -> Story:
    return Story(
        title="Stream Story",
        protagonista="X",
        relator="primera_persona",
        sinopsis="x",
        atmosfera="x",
    )


def _fake_director(num_beats: int):
    director = MagicMock()
    director.prompt_builder.num_beats = num_beats

    async def _execute_full(_story, **_kwargs):
        for i in range(1, num_beats + 1):
            yield _make_beat(i), None, 0.0

    director.execute_full = _execute_full
    return director


def _fake_story_repo():
    repo = MagicMock()
    repo.update_status = AsyncMock()
    repo.save_journal = AsyncMock()
    return repo


def _fake_beat_repo():
    repo = MagicMock()
    repo.save = AsyncMock()
    return repo


async def _collect_events(generator):
    return [event async for event in generator]


@pytest.mark.asyncio
async def test_stream_emits_done_with_narrative_id_when_use_case_injected():
    director = _fake_director(num_beats=2)
    story = _make_story()
    narrative_uc = MagicMock()
    saved_narrative = GeneratedNarrative(
        story_template_id=story.id,
        title="auto",
        content="prosa 1\n\nprosa 2",
        status=StoryStatus.COMPLETED,
    )
    narrative_uc.consolidate_and_save = AsyncMock(return_value=saved_narrative)

    events = await _collect_events(
        stream_story(
            director,
            story,
            story_repo=_fake_story_repo(),
            beat_repo=_fake_beat_repo(),
            narrative_use_case=narrative_uc,
        )
    )

    done_events = [e for e in events if e.event == StreamEventType.DONE]
    assert len(done_events) == 1
    assert done_events[0].data["narrative_id"] == str(saved_narrative.id)
    assert done_events[0].data["total_beats"] == 2
    narrative_uc.consolidate_and_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_emits_done_with_null_narrative_id_when_use_case_omitted():
    director = _fake_director(num_beats=1)
    story = _make_story()

    events = await _collect_events(
        stream_story(
            director,
            story,
            story_repo=_fake_story_repo(),
            beat_repo=_fake_beat_repo(),
        )
    )

    done_events = [e for e in events if e.event == StreamEventType.DONE]
    assert len(done_events) == 1
    assert done_events[0].data["narrative_id"] is None


@pytest.mark.asyncio
async def test_stream_continues_emitting_done_when_narrative_save_fails():
    director = _fake_director(num_beats=1)
    story = _make_story()
    broken_uc = MagicMock()
    broken_uc.consolidate_and_save = AsyncMock(side_effect=RuntimeError("boom"))

    events = await _collect_events(
        stream_story(
            director,
            story,
            story_repo=_fake_story_repo(),
            beat_repo=_fake_beat_repo(),
            narrative_use_case=broken_uc,
        )
    )

    done_events = [e for e in events if e.event == StreamEventType.DONE]
    error_events = [e for e in events if e.event == StreamEventType.ERROR]
    assert len(done_events) == 1
    assert done_events[0].data["narrative_id"] is None
    assert error_events == []
