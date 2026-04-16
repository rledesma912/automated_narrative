"""Story router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.presentation.schemas.request import StoryCreateRequest
from src.presentation.schemas.response import StoryResponse

router = APIRouter(tags=["Stories"])


def get_story_use_case():
    """Getter for use case (placeholder)."""
    from src.application.use_cases.create_story import CreateStoryUseCase
    from src.infrastructure.database.repositories import SQLStoryRepository

    repo = SQLStoryRepository()
    return CreateStoryUseCase(repo)


@router.post("/stories", response_model=StoryResponse, status_code=201)
async def create_story(
    request: StoryCreateRequest,
    use_case=Depends(get_story_use_case),
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
async def list_stories():
    """List all stories."""
    from src.infrastructure.database.repositories import SQLStoryRepository

    repo = SQLStoryRepository()
    stories = await repo.list_all()

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
async def get_story(story_id: str):
    """Get a story by ID."""
    from src.infrastructure.database.repositories import SQLStoryRepository

    repo = SQLStoryRepository()
    story = await repo.get_by_id(UUID(story_id))

    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    return StoryResponse(
        id=str(story.id),
        title=story.title,
        status=story.status.value,
        created_at=story.created_at,
    )
