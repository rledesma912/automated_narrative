"""Tests para GenerateNarrativesUseCase.consolidate_and_save (Spec-312)."""

import re
import uuid
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.domain.models import BeatStatus, GeneratedNarrative, MacroBeat, Story, StoryStatus


def _make_story(beats: list[MacroBeat]) -> Story:
    return Story(
        title="La Casa Vacía",
        protagonista="Ana",
        relator="primera_persona",
        sinopsis="x",
        atmosfera="x",
        beats=beats,
    )


def _make_beat(number: int, content: str) -> MacroBeat:
    return MacroBeat(
        number=number,
        summary=f"summary {number}",
        generated_act=content,
        status=BeatStatus.COMPLETED,
    )


@pytest.fixture
def use_case():
    uc = GenerateNarrativesUseCase()
    uc.narrative_repo = AsyncMock()
    uc.narrative_repo.save = AsyncMock(side_effect=lambda n: n)
    return uc


@pytest.mark.asyncio
async def test_consolidate_and_save_concatenates_beats_in_order(use_case):
    story = _make_story(
        [
            _make_beat(2, "segundo"),
            _make_beat(1, "primero"),
            _make_beat(3, "tercero"),
        ]
    )

    narrative = await use_case.consolidate_and_save(story)

    assert isinstance(narrative, GeneratedNarrative)
    # _consolidate_content usa '## Beat N - summary\n\n' como wrapper
    assert "primero" in narrative.content
    assert "segundo" in narrative.content
    assert "tercero" in narrative.content
    # Verifica que los beats están en orden numérico (1, 2, 3)
    p1 = narrative.content.find("primero")
    p2 = narrative.content.find("segundo")
    p3 = narrative.content.find("tercero")
    assert p1 < p2 < p3, "Los beats deben estar en orden numérico"
    assert narrative.story_template_id == story.id
    assert narrative.status == StoryStatus.COMPLETED


@pytest.mark.asyncio
async def test_consolidate_and_save_uses_default_title_when_none(use_case):
    story = _make_story([_make_beat(1, "x")])

    narrative = await use_case.consolidate_and_save(story)

    assert narrative.title.startswith(f"{story.title} · ")
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", narrative.title)


@pytest.mark.asyncio
async def test_consolidate_and_save_uses_explicit_title_when_provided(use_case):
    story = _make_story([_make_beat(1, "x")])

    narrative = await use_case.consolidate_and_save(story, title="Manual v1")

    assert narrative.title == "Manual v1"


@pytest.mark.asyncio
async def test_consolidate_and_save_raises_when_no_beats(use_case):
    story = _make_story([])

    with pytest.raises(ValueError, match="no tiene beats"):
        await use_case.consolidate_and_save(story)

    use_case.narrative_repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_consolidate_and_save_raises_when_all_beats_empty(use_case):
    story = _make_story([_make_beat(1, ""), _make_beat(2, "")])

    with pytest.raises(ValueError, match="no tiene prosa"):
        await use_case.consolidate_and_save(story)

    use_case.narrative_repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_consolidate_and_save_creates_new_uuid_each_call(use_case):
    """D1.c: cada corrida produce una variante nueva (UUID distinto)."""
    story = _make_story([_make_beat(1, "una vez")])

    n1 = await use_case.consolidate_and_save(story)
    n2 = await use_case.consolidate_and_save(story)

    assert n1.id != n2.id
    assert isinstance(n1.id, uuid.UUID)
    assert use_case.narrative_repo.save.await_count == 2


@pytest.mark.asyncio
async def test_update_content_preserves_id_and_title(use_case):
    """Spec-430: update_content sobrescribe content pero conserva id/título."""
    story = _make_story([_make_beat(1, "acto uno original")])
    existing = GeneratedNarrative(
        story_template_id=story.id,
        title="Mi variante",
        content="contenido viejo",
    )
    use_case.narrative_repo.get_by_id = AsyncMock(return_value=existing)

    story.beats = [_make_beat(1, "acto uno REGENERADO")]
    result = await use_case.update_content(existing.id, story)

    assert result.id == existing.id
    assert result.title == "Mi variante"
    assert "acto uno REGENERADO" in result.content
    assert "contenido viejo" not in result.content


@pytest.mark.asyncio
async def test_update_content_raises_when_narrative_not_found(use_case):
    story = _make_story([_make_beat(1, "x")])
    use_case.narrative_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="no encontrado"):
        await use_case.update_content(uuid.uuid4(), story)


@pytest.mark.asyncio
async def test_update_content_raises_when_narrative_belongs_to_other_story(use_case):
    story = _make_story([_make_beat(1, "x")])
    other_narrative = GeneratedNarrative(
        story_template_id=uuid.uuid4(),
        title="De otra historia",
        content="x",
    )
    use_case.narrative_repo.get_by_id = AsyncMock(return_value=other_narrative)

    with pytest.raises(ValueError, match="no pertenece"):
        await use_case.update_content(other_narrative.id, story)
