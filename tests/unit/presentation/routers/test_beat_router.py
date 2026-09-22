"""Tests para el endpoint POST /stories/{id}/beats/{n}/regenerate-voz (Spec-430)."""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.domain.exceptions import StoryNotFoundError
from src.domain.models import BeatStatus, GeneratedNarrative, MacroBeat
from src.presentation.routers.beat_router import regenerate_beat_voz
from src.presentation.schemas.request import BeatRegenerateRequest

_STORY_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_regenerate_beat_voz_success():
    use_case = AsyncMock()
    beat = MacroBeat(
        number=2, summary="evento", generated_act="prosa nueva", status=BeatStatus.COMPLETED
    )
    narrative_id = uuid.uuid4()
    narrative = GeneratedNarrative(
        id=narrative_id, story_template_id=_STORY_ID, title="v1", content="contenido nuevo"
    )
    use_case.execute.return_value = (beat, narrative)

    request = BeatRegenerateRequest(narrative_id=narrative_id)
    response = await regenerate_beat_voz(str(_STORY_ID), 2, request, use_case=use_case)

    assert response.beat.number == 2
    assert response.beat.content == "prosa nueva"
    assert response.narrative_id == str(narrative_id)
    assert response.narrative_content == "contenido nuevo"
    use_case.execute.assert_awaited_once_with(_STORY_ID, 2, narrative_id)


@pytest.mark.asyncio
async def test_regenerate_beat_voz_story_not_found_returns_404():
    use_case = AsyncMock()
    use_case.execute.side_effect = StoryNotFoundError("no existe")

    request = BeatRegenerateRequest(narrative_id=uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await regenerate_beat_voz(str(_STORY_ID), 2, request, use_case=use_case)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_regenerate_beat_voz_value_error_returns_400():
    use_case = AsyncMock()
    use_case.execute.side_effect = ValueError("Acto 9 no encontrado o no narrado aún")

    request = BeatRegenerateRequest(narrative_id=uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await regenerate_beat_voz(str(_STORY_ID), 9, request, use_case=use_case)

    assert exc_info.value.status_code == 400
    assert "no encontrado" in exc_info.value.detail
