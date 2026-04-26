"""GetStoryByIdUseCase — obtiene una historia por UUID."""

from uuid import UUID

from src.domain.interfaces import StoryRepository
from src.domain.models import Story


class GetStoryByIdUseCase:
    def __init__(self, story_repo: StoryRepository):
        self.story_repo = story_repo

    async def execute(self, story_id: UUID) -> Story | None:
        return await self.story_repo.get_by_id(story_id)
