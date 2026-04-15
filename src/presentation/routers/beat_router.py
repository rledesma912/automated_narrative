"""Beat router."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.presentation.schemas.response import BeatResponse
from src.presentation.schemas.request import BeatUpdateRequest

router = APIRouter(tags=["Beats"])


@router.get("/stories/{story_id}/beats", response_model=list[BeatResponse])
async def list_beats(story_id: str):
    """List all beats for a story."""
    from src.infrastructure.database.repositories import SQLBeatRepository

    repo = SQLBeatRepository()
    beats = await repo.get_by_story(UUID(story_id))

    return [
        BeatResponse(
            number=b.number,
            summary=b.summary,
            content=b.content,
            status=b.status,
        )
        for b in beats
    ]


@router.put("/stories/{story_id}/beats/{beat_number}")
async def update_beat(story_id: str, beat_number: int, request: BeatUpdateRequest):
    """Update a beat's summary."""
    from src.infrastructure.database.repositories import SQLBeatRepository

    repo = SQLBeatRepository()
    beat = await repo.get_by_number(UUID(story_id), beat_number)

    if not beat:
        raise HTTPException(
            status_code=404, detail=f"Beat no encontrado: {beat_number}"
        )

    beat.summary = request.summary
    await repo.update(beat, UUID(story_id))

    return {"status": "updated"}


@router.post("/stories/{story_id}/beats/{beat_number}", response_model=BeatResponse)
async def generate_beat(story_id: str, beat_number: int):
    """Generate content for a beat."""
    from src.infrastructure.database.repositories import (
        SQLStoryRepository,
        SQLBeatRepository,
    )
    from src.infrastructure.adapters import OllamaAdapter
    from src.application.use_cases.narrate_beat import NarrateBeatUseCase

    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()
    llm = OllamaAdapter()

    story = await story_repo.get_by_id(UUID(story_id))
    if not story:
        raise HTTPException(
            status_code=404, detail=f"Historia no encontrada: {story_id}"
        )

    beat = await beat_repo.get_by_number(UUID(story_id), beat_number)
    if not beat:
        raise HTTPException(
            status_code=404, detail=f"Beat no encontrado: {beat_number}"
        )

    use_case = NarrateBeatUseCase(llm)
    generated_beat, _ = await use_case.execute(story, beat)

    await beat_repo.update(generated_beat, UUID(story_id))

    return BeatResponse(
        number=generated_beat.number,
        summary=generated_beat.summary,
        content=generated_beat.content,
        status=generated_beat.status,
    )
