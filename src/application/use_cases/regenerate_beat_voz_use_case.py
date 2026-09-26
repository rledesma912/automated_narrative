"""RegenerateBeatVozUseCase - re-narra la Voz de un único acto (Spec-430, Spec-530 S7).

Usa el mismo prompt que la generación (el acto de la escaleta) con la memoria del
acto anterior: lo ya pasado y lo ya usado, para no repetirlo. 1 llamada LLM.
"""

import logging
from uuid import UUID

from src.application.services.authoring.outline_narrator import OutlineNarrator
from src.application.services.prompt_builder import PromptBuilder
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.application.use_cases.voz_use_case import VozUseCase
from src.domain.exceptions import StoryNotFoundError
from src.domain.interfaces import LLMProvider
from src.domain.models import GeneratedNarrative, MacroBeat
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository

logger = logging.getLogger(__name__)


class RegenerateBeatVozUseCase:
    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        story_repo: SQLStoryRepository,
        beat_repo: SQLBeatRepository,
        narrative_use_case: GenerateNarrativesUseCase,
        voz_use_case: VozUseCase | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.story_repo = story_repo
        self.beat_repo = beat_repo
        self.narrative_use_case = narrative_use_case
        self.voz = voz_use_case or VozUseCase(llm)

    async def execute(
        self, story_id: UUID, beat_number: int, narrative_id: UUID
    ) -> tuple[MacroBeat, GeneratedNarrative]:
        story = await self.story_repo.get_by_id(story_id)
        if not story:
            raise StoryNotFoundError(f"Historia no encontrada: {story_id}")

        beat = next((b for b in story.beats if b.number == beat_number), None)
        if not beat or not beat.has_content():
            raise ValueError(f"Acto {beat_number} no encontrado o no narrado aún")
        act = next((a for a in story.outline if a.number == beat_number), None)
        if act is None:
            raise ValueError(
                "La historia no tiene escaleta: generala de nuevo para poder regenerar un acto"
            )

        previous = None
        if beat_number > 1:
            previous = await self.story_repo.get_journal(story_id, beat_number - 1)

        narrator = OutlineNarrator(self.llm, self.prompt_builder)
        system_prompt, user_prompt = narrator.voice_prompts(story, act, previous)
        logger.debug(f"[REGEN-VOZ] beat={beat_number} story={story_id} narrative={narrative_id}")
        beat, _elapsed = await self.voz.narrate_with_prompts(beat, system_prompt, user_prompt)
        await self.beat_repo.update(beat, story_id)

        story.beats = [beat if b.number == beat_number else b for b in story.beats]
        narrative = await self.narrative_use_case.update_content(narrative_id, story)
        return beat, narrative
