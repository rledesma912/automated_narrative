"""Spec-490 T1.1: GenerateNarrativesUseCase.export_tts_markdown."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.domain.models import GeneratedNarrative, Story
from src.utils import ARGENTINA_TZ

_CREATED = datetime(2026, 9, 24, 15, 30, tzinfo=ARGENTINA_TZ)


def _narrative(title: str = "El monte prohibido · 2026-09-24 15:30") -> GeneratedNarrative:
    return GeneratedNarrative(
        story_template_id=uuid.uuid4(),
        title=title,
        content="## Acto 1\n\n- ¿Quién anda ahí?",
        created_at=_CREATED,
    )


def _use_case(
    narrative: GeneratedNarrative | None, story: Story | None
) -> GenerateNarrativesUseCase:
    uc = GenerateNarrativesUseCase()
    uc.narrative_repo = AsyncMock()
    uc.narrative_repo.get_by_id = AsyncMock(return_value=narrative)
    uc.story_repo = AsyncMock()
    uc.story_repo.get_by_id = AsyncMock(return_value=story)
    return uc


@pytest.mark.asyncio
async def test_usa_el_titulo_de_la_historia():
    story = Story(title="El monte prohibido", protagonista="x", relator="x", sinopsis="x")
    narrative = _narrative(title="Variante editada · 2026-09-24 15:30")
    uc = _use_case(narrative, story)

    filename, markdown = await uc.export_tts_markdown(narrative.id)

    assert filename == "el-monte-prohibido-2026-09-24-1530.md"
    assert markdown == "# El monte prohibido\n\n## Acto 1\n\n—¿Quién anda ahí?\n"
    uc.story_repo.get_by_id.assert_awaited_once_with(narrative.story_template_id)


@pytest.mark.asyncio
async def test_historia_borrada_usa_el_titulo_de_la_variante_sin_fecha():
    uc = _use_case(_narrative(title="La pena · del colectivo · 2026-09-24 15:30"), None)

    filename, markdown = await uc.export_tts_markdown(uuid.uuid4())

    assert filename == "la-pena-del-colectivo-2026-09-24-1530.md"
    assert markdown.startswith("# La pena · del colectivo\n")


@pytest.mark.asyncio
async def test_variante_inexistente():
    uc = _use_case(None, None)

    assert await uc.export_tts_markdown(uuid.uuid4()) is None
    uc.story_repo.get_by_id.assert_not_awaited()
