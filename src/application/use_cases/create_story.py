"""CreateStoryUseCase - crea una nueva historia."""

from src.application.dto import StoryCreateDTO
from src.domain.interfaces import StoryRepository
from src.domain.models import Story, StoryStatus


class CreateStoryUseCase:
    """Caso de uso para crear una historia."""

    def __init__(self, story_repository: StoryRepository):
        self.story_repository = story_repository

    async def execute(self, dto: StoryCreateDTO) -> Story:
        """Crea una nueva historia."""
        story = Story(
            title=dto.title,
            protagonista=dto.protagonista,
            relator=dto.relator,
            escenarios=dto.escenarios,
            sinopsis=dto.sinopsis,
            atmosfera=dto.atmosfera,
            reglas=dto.reglas,
            status=StoryStatus.PENDING,
        )

        return await self.story_repository.save(story)
