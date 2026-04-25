"""CreateStoryUseCase - crea una nueva historia."""

from src.application.dto import StoryCreateDTO
from src.domain.interfaces import StoryRepository
from src.domain.models import Scenario, Story, StoryStatus


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
            sinopsis=dto.sinopsis,
            atmosfera=dto.atmosfera,
            reglas=dto.reglas,
            status=StoryStatus.PENDING,
        )

        # Crear objetos Scenario
        if dto.escenarios:
            story.scenarios = [
                Scenario(story_id=story.id, order_index=i, name=name)
                for i, name in enumerate(dto.escenarios)
            ]

        return await self.story_repository.save(story)
