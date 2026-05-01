"""CreateStoryUseCase - crea una nueva historia."""

from uuid import uuid4

from src.application.dto import StoryCreateDTO
from src.domain.interfaces import StoryRepository
from src.domain.models import RuleType, Scenario, Story, StoryStatus, TypedRule


class CreateStoryUseCase:
    """Caso de uso para crear una historia."""

    def __init__(self, story_repository: StoryRepository):
        self.story_repository = story_repository

    async def execute(self, dto: StoryCreateDTO, initial_status: StoryStatus = StoryStatus.DRAFT) -> Story:
        """Crea una nueva historia."""
        story = Story(
            title=dto.title,
            protagonista=dto.protagonista,
            relator=dto.relator,
            sinopsis=dto.sinopsis,
            atmosfera=dto.atmosfera,
            reglas=dto.reglas,
            status=initial_status,
            storyteller_config=dto.storyteller_config,
            personajes_full=dto.personajes_full,
        )

        # Crear objetos Scenario
        if dto.escenarios:
            story.scenarios = [
                Scenario(story_id=story.id, order_index=i, name=name)
                for i, name in enumerate(dto.escenarios)
            ]

        # Crear TypedRule si el DTO trae reglas tipadas
        if dto.typed_rules:
            typed = []
            for r in dto.typed_rules:
                raw_type = r.get("type")
                try:
                    rule_type = RuleType(raw_type) if raw_type else None
                except ValueError:
                    rule_type = None
                typed.append(TypedRule(
                    id=r.get("id") or str(uuid4()),
                    story_id=story.id,
                    content=r.get("content", ""),
                    type=rule_type,
                    intensity=r.get("intensity"),
                ))
            story.typed_rules = typed

        return await self.story_repository.save(story)
