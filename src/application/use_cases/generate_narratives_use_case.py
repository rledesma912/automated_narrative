"""GenerateNarrativesUseCase - genera múltiples relatos a partir de una plantilla."""

import logging
from uuid import UUID

from src.domain.models import GeneratedNarrative, Story, StoryStatus
from src.infrastructure.database.repositories import (
    SQLBeatRepository,
    SQLGeneratedNarrativeRepository,
    SQLStoryRepository,
)
from src.utils.timezone import now_argentina

logger = logging.getLogger(__name__)


class GenerateNarrativesUseCase:
    """Caso de uso para generar múltiples relatos a partir de una StoryTemplate."""

    def __init__(self):
        self.narrative_repo = SQLGeneratedNarrativeRepository()
        self.story_repo = SQLStoryRepository()
        self.beat_repo = SQLBeatRepository()

    @staticmethod
    def _default_title(story: Story) -> str:
        ts = now_argentina().strftime("%Y-%m-%d %H:%M")
        return f"{story.title} · {ts}"

    @staticmethod
    def _consolidate_content(story: Story) -> str:
        parts = []
        for beat in sorted(story.beats, key=lambda b: b.number):
            if beat.content:
                beat_title = f"Beat {beat.number}"
                if beat.summary:
                    beat_title += f" - {beat.summary}"
                parts.append(f"## {beat_title}\n\n{beat.content}")
        return "\n\n".join(parts)

    async def consolidate_and_save(
        self, story: Story, title: str | None = None
    ) -> GeneratedNarrative:
        """Consolida los beats narrados de `story` y persiste una nueva variante.

        Spec-312 D1.c: cada llamada crea una fila nueva (UUID nuevo). Pensado
        para invocarse desde StoryRunner / stream_story al finalizar la generación.
        """
        if not story.beats:
            raise ValueError(f"La historia {story.id} no tiene beats para consolidar")

        full_content = self._consolidate_content(story)
        if not full_content:
            raise ValueError(f"La historia {story.id} no tiene prosa generada en sus beats")

        narrative = GeneratedNarrative(
            story_template_id=story.id,
            title=title or self._default_title(story),
            content=full_content,
            status=StoryStatus.COMPLETED,
        )
        return await self.narrative_repo.save(narrative)

    async def generate_from_existing_beats(self, story_id: UUID, title: str) -> GeneratedNarrative:
        """Genera un nuevo relato usando los beats existentes de la story.

        Consolida los beats en un solo contenido narrativo.
        """
        story = await self.story_repo.get_by_id(story_id)
        if not story:
            raise ValueError(f"Story no encontrada: {story_id}")

        return await self.consolidate_and_save(story, title=title)

    async def list_by_story_template(self, story_template_id: UUID) -> list[GeneratedNarrative]:
        """Lista todos los relatos generados para una plantilla."""
        return await self.narrative_repo.get_by_story_template_id(story_template_id)

    async def get_by_id(self, narrative_id: UUID) -> GeneratedNarrative | None:
        """Obtiene un relato generado por su ID."""
        return await self.narrative_repo.get_by_id(narrative_id)

    async def delete(self, narrative_id: UUID) -> None:
        """Elimina un relato generado."""
        await self.narrative_repo.delete(narrative_id)
