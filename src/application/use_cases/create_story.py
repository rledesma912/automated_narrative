"""CreateStoryUseCase - crea una nueva historia."""

from uuid import uuid4

from src.application.dto import StoryCreateDTO
from src.domain.interfaces import StoryRepository
from src.domain.models import BeatType, MacroBeat, RuleType, Scenario, Story, StoryStatus, TypedRule


class CreateStoryUseCase:
    """Caso de uso para crear una historia."""

    def __init__(self, story_repository: StoryRepository):
        self.story_repository = story_repository

    async def execute(
        self, dto: StoryCreateDTO, initial_status: StoryStatus = StoryStatus.DRAFT
    ) -> Story:
        """Crea una nueva historia."""
        story = Story(
            title=dto.title,
            protagonista=dto.protagonista,
            relator=dto.relator,
            sinopsis=dto.sinopsis,
            genero=dto.genero,
            subgenero=dto.subgenero,
            tono=dto.tono,
            reglas=dto.reglas,
            status=initial_status,
            narrator_config=dto.narrator_config,
            personajes_full=dto.personajes_full,
        )

        # Crear objetos Scenario. Si el DTO trae escenarios_full (con
        # description), se prefiere; si no, se cae a la lista de nombres.
        if dto.escenarios_full:
            story.scenarios = [
                Scenario(
                    story_id=story.id,
                    order_index=i,
                    name=s.get("name", ""),
                    description=s.get("description", ""),
                )
                for i, s in enumerate(dto.escenarios_full)
            ]
        elif dto.escenarios:
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
                typed.append(
                    TypedRule(
                        id=r.get("id") or str(uuid4()),
                        story_id=story.id,
                        content=r.get("content", ""),
                        type=rule_type,
                        intensity=r.get("intensity"),
                    )
                )
            story.typed_rules = typed

        # Pre-crear los 5 MacroBeat desde los actos del YAML (Spec-190 T7.1)
        if dto.actos:
            beats = []
            for act in dto.actos:
                number = act.get("number", 1)
                beat_type_str = act.get("type", "")
                try:
                    beat_type = BeatType(beat_type_str) if beat_type_str else None
                except ValueError:
                    beat_type = None
                beats.append(
                    MacroBeat(
                        number=number,
                        summary=f"Acto {number}: {beat_type_str}",
                        beat_type=beat_type,
                        synopsis_beat=act.get("synopsis", ""),
                    )
                )
            story.beats = beats

        return await self.story_repository.save(story)
