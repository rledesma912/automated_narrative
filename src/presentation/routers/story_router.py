"""Story router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.application.dto import StoryCreateDTO
from src.application.use_cases import GetStoryByIdUseCase, ListStoriesUseCase
from src.application.use_cases.create_story import CreateStoryUseCase
from src.domain.models import StoryStatus
from src.infrastructure.database.repositories import SQLStoryRepository
from src.presentation.schemas.request import StoryCreateRequest
from src.presentation.schemas.response import StoryResponse

router = APIRouter(tags=["Stories"])


def _story_repo() -> SQLStoryRepository:
    return SQLStoryRepository()


def get_create_story_use_case(repo=Depends(_story_repo)) -> CreateStoryUseCase:
    return CreateStoryUseCase(repo)


def get_list_stories_use_case(repo=Depends(_story_repo)) -> ListStoriesUseCase:
    return ListStoriesUseCase(repo)


def get_story_by_id_use_case(repo=Depends(_story_repo)) -> GetStoryByIdUseCase:
    return GetStoryByIdUseCase(repo)


def _request_to_dto(req: StoryCreateRequest) -> StoryCreateDTO:
    """Traduce StoryCreateRequest (capa presentación) → StoryCreateDTO (capa aplicación).

    Resuelve tres incompatibilidades entre capas:
    1. escenarios: str → list[str]  (usa storyteller_config.scenarios si existe)
    2. typed_rules: ausente en request → list[dict] desde storyteller_config.rules
    3. rules[].text → content  (campo renombrado entre frontend y use case)
    """
    sc: dict = req.storyteller_config or {}

    # 1. Escenarios: preferir estructura rica de storyteller_config, fallback al string
    raw_scenarios: list[dict] = sc.get("scenarios") or []
    if raw_scenarios:
        escenarios_list = [s.get("name", "") for s in raw_scenarios if s.get("name")]
    else:
        escenarios_list = [
            chunk.split(":")[0].strip()
            for chunk in (req.escenarios or "").split(";")
            if chunk.strip()
        ]

    # 2. Typed rules: desde storyteller_config.rules, mapeando text → content
    raw_rules: list[dict] = sc.get("rules") or []
    typed_rules = [
        {
            "id":      r.get("id", ""),
            "content": r.get("text") or r.get("content", ""),
            "type":    r.get("type", ""),
        }
        for r in raw_rules
        if r.get("text") or r.get("content")
    ]

    return StoryCreateDTO(
        title=req.title,
        protagonista=req.protagonista,
        relator=req.relator,
        escenarios=escenarios_list,
        sinopsis=req.sinopsis,
        atmosfera=req.atmosfera,
        reglas=req.reglas,
        storyteller_config=req.storyteller_config,
        typed_rules=typed_rules,
        personajes_full=req.personajes_full,
    )


@router.post("/stories", response_model=StoryResponse, status_code=201)
async def create_story(
    request: StoryCreateRequest,
    action: str = "generate",
    use_case: CreateStoryUseCase = Depends(get_create_story_use_case),
):
    """Create a new story. action=save → draft; action=generate → pending."""
    try:
        dto = _request_to_dto(request)
        initial_status = StoryStatus.DRAFT if action == "save" else StoryStatus.PENDING
        story = await use_case.execute(dto, initial_status=initial_status)
        return StoryResponse(
            id=str(story.id),
            title=story.title,
            status=story.status.value,
            created_at=story.created_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stories", response_model=list[StoryResponse])
async def list_stories(
    use_case: ListStoriesUseCase = Depends(get_list_stories_use_case),
):
    """List all stories."""
    stories = await use_case.execute()
    return [
        StoryResponse(
            id=str(s.id),
            title=s.title,
            status=s.status.value,
            created_at=s.created_at,
            atmosfera=s.atmosfera,
            protagonista=s.protagonista,
        )
        for s in stories
    ]


@router.get("/stories/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: str,
    use_case: GetStoryByIdUseCase = Depends(get_story_by_id_use_case),
):
    """Get a story by ID."""
    story = await use_case.execute(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")
    return StoryResponse(
        id=str(story.id),
        title=story.title,
        status=story.status.value,
        created_at=story.created_at,
        atmosfera=story.atmosfera,
        protagonista=story.protagonista,
        relator=story.relator,
        sinopsis=story.sinopsis,
        storyteller_config=story.storyteller_config,
        personajes_full=story.personajes_full,
    )
