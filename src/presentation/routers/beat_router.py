"""Beat router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.application.services.prompt_builder import PromptBuilder
from src.application.use_cases import ListBeatsUseCase, UpdateBeatUseCase
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.application.use_cases.regenerate_beat_voz_use_case import RegenerateBeatVozUseCase
from src.domain.exceptions import StoryNotFoundError
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.presentation.schemas.request import BeatRegenerateRequest, BeatUpdateRequest
from src.presentation.schemas.response import BeatRegenerateResponse, BeatResponse

router = APIRouter(tags=["Beats"])


def _beat_repo() -> SQLBeatRepository:
    return SQLBeatRepository()


def get_list_beats_use_case(repo=Depends(_beat_repo)) -> ListBeatsUseCase:
    return ListBeatsUseCase(repo)


def get_update_beat_use_case(repo=Depends(_beat_repo)) -> UpdateBeatUseCase:
    return UpdateBeatUseCase(repo)


def get_regenerate_beat_use_case() -> RegenerateBeatVozUseCase:
    llm = LLMFactory.get_provider()
    prompt_builder = PromptBuilder()
    return RegenerateBeatVozUseCase(
        llm=llm,
        prompt_builder=prompt_builder,
        story_repo=SQLStoryRepository(),
        beat_repo=SQLBeatRepository(),
        narrative_use_case=GenerateNarrativesUseCase(),
    )


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
            content=b.generated_act,
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


@router.post(
    "/stories/{story_id}/beats/{beat_number}/regenerate-voz",
    response_model=BeatRegenerateResponse,
)
async def regenerate_beat_voz(
    story_id: str,
    beat_number: int,
    request: BeatRegenerateRequest,
    use_case: RegenerateBeatVozUseCase = Depends(get_regenerate_beat_use_case),
):
    """Regenera solo la Voz (prosa) de un acto ya narrado (Spec-430).

    No re-ejecuta Mapper ni Journal: reutiliza el evento/escenario ya extraídos
    y el journal ya persistido. 1 sola llamada LLM.
    """
    try:
        beat, narrative = await use_case.execute(UUID(story_id), beat_number, request.narrative_id)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return BeatRegenerateResponse(
        beat=BeatResponse(
            number=beat.number,
            summary=beat.summary,
            content=beat.generated_act,
            status=beat.status,
        ),
        narrative_id=str(narrative.id),
        narrative_content=narrative.content,
    )
