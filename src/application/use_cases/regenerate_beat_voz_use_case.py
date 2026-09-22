"""RegenerateBeatVozUseCase - re-narra la Voz de un único acto (Spec-430)."""

import logging
from uuid import UUID

from src.application.services.prompt_builder import PromptBuilder
from src.application.services.story_analyst_service import StoryAnalystService
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.application.use_cases.voz_use_case import VozUseCase
from src.domain.exceptions import StoryNotFoundError
from src.domain.interfaces import LLMProvider
from src.domain.models import GeneratedNarrative, MacroBeat
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository

logger = logging.getLogger(__name__)


class RegenerateBeatVozUseCase:
    """Re-narra la Voz de un único acto ya generado, sin tocar Mapper ni Journal.

    Reutiliza el summary/escenario ya extraídos por el Mapper y el journal ya
    persistido para el acto anterior; solo dispara 1 llamada LLM (la Voz).
    """

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        story_repo: SQLStoryRepository,
        beat_repo: SQLBeatRepository,
        narrative_use_case: GenerateNarrativesUseCase,
        voz_use_case: VozUseCase | None = None,
        analyst_service: StoryAnalystService | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.story_repo = story_repo
        self.beat_repo = beat_repo
        self.narrative_use_case = narrative_use_case
        self.voz = voz_use_case or VozUseCase(llm, prompt_builder=prompt_builder)
        self.analyst = analyst_service or StoryAnalystService(llm, prompt_builder)

    async def execute(
        self, story_id: UUID, beat_number: int, narrative_id: UUID
    ) -> tuple[MacroBeat, GeneratedNarrative]:
        story = await self.story_repo.get_by_id(story_id)
        if not story:
            raise StoryNotFoundError(f"Historia no encontrada: {story_id}")

        beat = next((b for b in story.beats if b.number == beat_number), None)
        if not beat or not beat.has_content():
            raise ValueError(f"Acto {beat_number} no encontrado o no narrado aún")

        anchors = await self.story_repo.get_narrative_anchors(story_id)
        if not anchors:
            raise ValueError(f"Historia {story_id} no tiene anclajes narrativos persistidos")

        beat_anchors = self.analyst.resolve_beat_anchors(anchors, beat_number)

        previous_journal = None
        if beat_number > 1:
            previous_journal = await self.story_repo.get_journal(story_id, beat_number - 1)

        active_rules = story.active_rules_for_beat(beat_number)

        beat.user_prompt = self.prompt_builder.build_narrative_context(
            beat, beat_anchors, previous_journal, story=story, active_rules=active_rules
        )

        logger.debug(f"[REGEN-VOZ] beat={beat_number} story={story_id} narrative={narrative_id}")

        beat, _elapsed = await self.voz.narrate(beat, story)
        await self.beat_repo.update(beat, story_id)

        story.beats = [beat if b.number == beat_number else b for b in story.beats]
        narrative = await self.narrative_use_case.update_content(narrative_id, story)

        return beat, narrative
