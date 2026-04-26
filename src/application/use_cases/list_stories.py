"""ListStoriesUseCase — lista todas las historias."""

from src.domain.interfaces import StoryRepository
from src.domain.models import Story


class ListStoriesUseCase:
    def __init__(self, story_repo: StoryRepository):
        self.story_repo = story_repo

    async def execute(self) -> list[Story]:
        return await self.story_repo.list_all()
