"""Beat router: la prosa de cada acto (macro_beat) con su resumen desde la escaleta."""

from uuid import UUID

from fastapi import APIRouter, Depends

from src.application.use_cases import ListBeatsUseCase
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.presentation.schemas.response import BeatResponse

router = APIRouter(tags=["Beats"])


def _beat_repo() -> SQLBeatRepository:
    return SQLBeatRepository()


def get_list_beats_use_case(repo=Depends(_beat_repo)) -> ListBeatsUseCase:
    return ListBeatsUseCase(repo)


def outline_summaries(story) -> dict[int, str]:
    """Spec-570: el resumen de un acto son los hechos de su escaleta."""
    return {a.number: "; ".join(a.events) for a in (story.outline if story else [])}


@router.get("/stories/{story_id}/beats", response_model=list[BeatResponse])
async def list_beats(
    story_id: str,
    use_case: ListBeatsUseCase = Depends(get_list_beats_use_case),
):
    """La prosa de cada acto, con el resumen que sale de la escaleta."""
    beats = await use_case.execute(UUID(story_id))
    summaries = outline_summaries(await SQLStoryRepository().get_by_id(UUID(story_id)))
    return [
        BeatResponse(
            number=b.number,
            summary=summaries.get(b.number, ""),
            content=b.generated_act,
            status=b.status,
        )
        for b in beats
    ]
