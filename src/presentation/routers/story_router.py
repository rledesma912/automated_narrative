"""Story router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.application.use_cases import GetStoryByIdUseCase, ListStoriesUseCase
from src.application.use_cases.create_story import CreateStoryUseCase
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


@router.post("/stories", response_model=StoryResponse, status_code=201)
async def create_story(
    request: StoryCreateRequest,
    use_case: CreateStoryUseCase = Depends(get_create_story_use_case),
):
    """Create a new story."""
    try:
        story = await use_case.execute(request)
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
    )
