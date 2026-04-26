"""UpdateBeatUseCase — actualiza el summary de un beat."""

from uuid import UUID

from src.domain.exceptions import StoryNotFoundError
from src.domain.interfaces import BeatRepository
from src.domain.models import Beat


class UpdateBeatUseCase:
    def __init__(self, beat_repo: BeatRepository):
        self.beat_repo = beat_repo

    async def execute(self, story_id: UUID, beat_number: int, new_summary: str) -> Beat:
        beat = await self.beat_repo.get_by_number(story_id, beat_number)
        if beat is None:
            raise StoryNotFoundError(str(beat_number))
        beat.summary = new_summary
        await self.beat_repo.update(beat, story_id)
        return beat
