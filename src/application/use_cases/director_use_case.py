"""DirectorUseCase - orquestador LLM punta a punta."""

import logging
from collections.abc import AsyncIterator
from time import perf_counter
from typing import TYPE_CHECKING, Callable

from src.application.services import MemoryJournalist, PromptBuilder
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.use_cases.synopsis_beat_mapper import SynopsisBeatMapper
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, NarrativeJournal, Story, StoryPlan
from src.infrastructure.normalizers import ResponseNormalizer

if TYPE_CHECKING:
    from src.application.use_cases.voz_use_case import VozUseCase

logger = logging.getLogger(__name__)


class DirectorUseCase:
    """Orquestador de la generación de historias punta a punta.

    Responsabilidades:
    - execute()           → planificación solamente (CLI `plan`)
    - execute_full()      → plan + narración + journal, beat-by-beat (AsyncGenerator)
    - execute_narration() → narración sobre beats pre-existentes (AsyncGenerator)
    """

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        normalizer: ResponseNormalizer | None = None,
        debug_collector: DebugCollector | None = None,
        voz: "VozUseCase | None" = None,
        journalist: MemoryJournalist | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()
        self._voz = voz
        self._journalist = journalist

    def _get_voz(self) -> "VozUseCase":
        if self._voz is None:
            from src.application.use_cases.voz_use_case import VozUseCase
            journalist = self._get_journalist()
            self._voz = VozUseCase(
                self.llm,
                memory_journalist=journalist,
                prompt_builder=self.prompt_builder,
                normalizer=self.normalizer,
                debug_collector=self.debug_collector,
            )
        return self._voz

    def _get_journalist(self) -> MemoryJournalist:
        if self._journalist is None:
            self._journalist = MemoryJournalist(
                self.llm,
                prompt_builder=self.prompt_builder,
                debug_collector=self.debug_collector,
            )
        return self._journalist

    async def execute(self, story: Story) -> StoryPlan:
        """Planificación solamente. Usado por CLI `plan`."""
        mapper = SynopsisBeatMapper(
            self.llm,
            self.prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
        )

        logger.debug(
            f"[DIRECTOR] Planificación via mapper — "
            f"prompt_builder={self.prompt_builder.__class__.__name__}",
        )

        beats = await mapper.map(story)
        logger.debug(f"[DIRECTOR] Plan generado: {len(beats)} beats")

        return StoryPlan(story_id=story.id, title=story.title, beats=beats)

    async def execute_full(
        self,
        story: Story,
        initial_journal: NarrativeJournal | None = None,
        on_plan_ready: Callable[[int, float], None] | None = None,
    ) -> AsyncIterator[tuple[Beat, NarrativeJournal, float]]:
        """Orquestación punta a punta: plan → narración beat-by-beat.

        Yields (beat_completado, journal_actualizado, llm_elapsed) por cada beat.
        """
        mapper = SynopsisBeatMapper(
            self.llm,
            self.prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
        )

        t0 = perf_counter()
        beats = await mapper.map(story)
        plan_elapsed = perf_counter() - t0

        logger.debug(f"[DIRECTOR] Plan: {len(beats)} beats en {plan_elapsed:.1f}s")

        if on_plan_ready is not None:
            on_plan_ready(len(beats), plan_elapsed)

        async for item in self.execute_narration(story, beats, initial_journal):
            yield item

    async def execute_narration(
        self,
        story: Story,
        beats_to_narrate: list[Beat],
        initial_journal: NarrativeJournal | None = None,
    ) -> AsyncIterator[tuple[Beat, NarrativeJournal, float]]:
        """Narra una lista de beats pre-existentes.

        Yields (beat_completado, journal_actualizado, llm_elapsed) por cada beat.
        """
        voz = self._get_voz()
        journal = initial_journal
        completed: list[Beat] = []

        for beat in beats_to_narrate:
            logger.debug(f"[DIRECTOR] Narrando beat #{beat.number}")
            beat, journal, llm_elapsed = await voz.execute(
                story=story,
                beat=beat,
                previous_beats=completed,
                journal=journal,
            )
            completed.append(beat)
            yield beat, journal, llm_elapsed


# Alias para backwards compatibility
CreateStoryPlanUseCase = DirectorUseCase
