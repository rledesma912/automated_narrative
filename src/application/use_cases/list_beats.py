"""ListBeatsUseCase — lista los beats de una historia."""

from uuid import UUID

from src.domain.interfaces import BeatRepository
from src.domain.models import ActText


class ListBeatsUseCase:
    def __init__(self, beat_repo: BeatRepository):
        self.beat_repo = beat_repo

    async def execute(self, story_id: UUID) -> list[ActText]:
        return await self.beat_repo.get_by_story(story_id)
