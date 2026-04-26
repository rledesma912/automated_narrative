"""Beat router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.application.use_cases import ListBeatsUseCase, UpdateBeatUseCase
from src.domain.exceptions import StoryNotFoundError
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.presentation.schemas.request import BeatUpdateRequest
from src.presentation.schemas.response import BeatResponse

router = APIRouter(tags=["Beats"])


def _beat_repo() -> SQLBeatRepository:
    return SQLBeatRepository()


def get_list_beats_use_case(repo=Depends(_beat_repo)) -> ListBeatsUseCase:
    return ListBeatsUseCase(repo)


def get_update_beat_use_case(repo=Depends(_beat_repo)) -> UpdateBeatUseCase:
    return UpdateBeatUseCase(repo)


@router.get("/stories/{story_id}/beats", response_model=list[BeatResponse])
async def list_beats(
    story_id: str,
    use_case: ListBeatsUseCase = Depends(get_list_beats_use_case),
):
    """List all beats for a story."""
    beats = await use_case.execute(UUID(story_id))
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
async def update_beat(
    story_id: str,
    beat_number: int,
    request: BeatUpdateRequest,
    use_case: UpdateBeatUseCase = Depends(get_update_beat_use_case),
):
    """Update a beat's summary."""
    try:
        await use_case.execute(UUID(story_id), beat_number, request.summary)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail=f"Beat no encontrado: {beat_number}")
    return {"status": "updated"}


@router.post("/stories/{story_id}/beats/{beat_number}", response_model=BeatResponse)
async def generate_beat(story_id: str, beat_number: int):
    """Generate content for a beat."""
    from src.application.use_cases.voz_use_case import VozUseCase
    from src.infrastructure.adapters import OllamaAdapter

    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()
    llm = OllamaAdapter()

    story = await story_repo.get_by_id(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    beat = await beat_repo.get_by_number(UUID(story_id), beat_number)
    if not beat:
        raise HTTPException(status_code=404, detail=f"Beat no encontrado: {beat_number}")

    use_case = VozUseCase(llm)
    generated_beat, _ = await use_case.execute(story, beat)

    await beat_repo.update(generated_beat, UUID(story_id))

    return BeatResponse(
        number=generated_beat.number,
        summary=generated_beat.summary,
        content=generated_beat.content,
        status=generated_beat.status,
    )
