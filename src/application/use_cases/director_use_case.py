"""DirectorUseCase - orquestador LLM punta a punta."""

import logging
from collections.abc import AsyncIterator
from time import perf_counter
from typing import TYPE_CHECKING, Callable

from src.application.services import MemoryJournalist, PromptBuilder
from src.application.services.checkpoint import VALID_CHECKPOINTS, ordinal
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.use_cases.synopsis_beat_mapper import SynopsisBeatMapper
from src.domain.interfaces import LLMProvider
from src.domain.models import (
    Beat,
    BeatStatus,
    BeatType,
    MacroBeat,
    NarrativeJournal,
    Story,
)
from src.infrastructure.normalizers import ResponseNormalizer

if TYPE_CHECKING:
    from src.application.use_cases.voz_use_case import VozUseCase

logger = logging.getLogger(__name__)


class DirectorUseCase:
    """Orquestador de la generación de historias punta a punta.

    Responsabilidades:
    - prepare_story()     → fase global analyst + resolver (planificación)
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
        story_repo=None,
        analyst_service=None,
        resolver_service=None,
        beat_mapper=None,
    ):
        from src.application.use_cases.voz_use_case import VozUseCase

        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()
        self.story_repo = story_repo
        self._analyst_service = analyst_service
        self._resolver_service = resolver_service
        self._beat_mapper = beat_mapper

        self._journalist = journalist or MemoryJournalist(
            llm,
            prompt_builder=prompt_builder,
            debug_collector=self.debug_collector,
        )
        self._voz = voz or VozUseCase(
            llm,
            memory_journalist=self._journalist,
            prompt_builder=prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
        )

    async def prepare_story(
        self,
        story: Story,
        on_analyst_done: Callable[[str], None] | None = None,
        on_resolver_done: Callable[[str], None] | None = None,
    ) -> tuple[dict, dict, int]:
        """Fase global: analyst + resolver → anclajes, distribución y número de beats.

        Extrae los anclajes narrativos y distribuye reglas/escenarios por beat.
        Se puede llamar independientemente de execute_full para hacer only-plan
        o para prepare-and-narrate (regeneración por acto).

        Returns:
            (narrative_anchors, rule_distribution, num_beats)

        Args:
            story: Historia a preparar.
            on_analyst_done: Callback cuando termina analyst (para reporter).
            on_resolver_done: Callback cuando termina resolver (para reporter).
        """
        from src.application.services.rule_scenario_resolver_service import (
            RuleScenarioResolverService,
        )
        from src.application.services.story_analyst_service import StoryAnalystService

        analyst = self._analyst_service or StoryAnalystService(
            self.llm, self.prompt_builder, self.normalizer, self.debug_collector
        )

        if on_analyst_done:
            on_analyst_done("Analizando sinopsis y anclajes")
        t_analyst = perf_counter()
        narrative_anchors = await analyst.extract_anchors(story)
        analyst_elapsed = perf_counter() - t_analyst

        if self.story_repo is not None:
            await self.story_repo.save_narrative_anchors(story.id, narrative_anchors)

        if on_analyst_done:
            on_analyst_done(f"Analizando sinopsis y anclajes ({analyst_elapsed:.1f}s)")

        resolver = self._resolver_service or RuleScenarioResolverService(
            self.llm, self.prompt_builder, self.normalizer, self.debug_collector
        )

        if on_resolver_done:
            on_resolver_done("Distribuyendo reglas y escenarios")
        t_resolver = perf_counter()
        rule_distribution = await resolver.resolve_distribution(story, anchors=narrative_anchors)
        resolver_elapsed = perf_counter() - t_resolver

        if on_resolver_done:
            on_resolver_done(f"Distribuyendo reglas y escenarios ({resolver_elapsed:.1f}s)")

        num_beats = self.prompt_builder.num_beats
        logger.debug(
            f"[DIRECTOR] Anclajes extraídos → {num_beats} beats "
            f"(analyst {analyst_elapsed:.1f}s, resolver {resolver_elapsed:.1f}s)"
        )

        return narrative_anchors, rule_distribution, num_beats

    async def execute_full(
        self,
        story: Story,
        initial_journal: NarrativeJournal | None = None,
        on_plan_ready: Callable[[int, float], None] | None = None,
        on_step_done: Callable[[str, float], None] | None = None,
        on_step_start: Callable[[str], None] | None = None,
        stop_after: str | None = None,
    ) -> AsyncIterator[tuple[MacroBeat, NarrativeJournal, float]]:
        """Orquestación punta a punta (Spec-038): ANALYST → 5×(MAPPER+NC+VOZ+JOURNAL).

        Yields (macro_beat_completado, journal_actualizado, llm_elapsed_voz) por beat.

        Args:
            story: Historia a generar.
            initial_journal: Journal inicial (para resumed).
            on_plan_ready: Callback cuando el plan está listo.
            on_step_done: Callback para pasos intermedios (Spec-043).
            stop_after: Checkpoint para detener el pipeline (Spec-040).
                Valores: analyst, mapper:1..5, voz:1..5, journal:1..5.
        """
        stop_at: int | None = VALID_CHECKPOINTS.get(stop_after) if stop_after else None

        def _step_start(msg: str) -> None:
            if on_step_start:
                on_step_start(msg)

        def _analyst_done(msg: str) -> None:
            if on_step_done:
                on_step_done("Analizando sinopsis y anclajes", 0)
            _step_start(msg)

        def _resolver_done(msg: str) -> None:
            if on_step_done:
                on_step_done("Distribuyendo reglas y escenarios", 0)
            _step_start(msg)

        narrative_anchors, rule_distribution, num_beats = await self.prepare_story(
            story,
            on_analyst_done=_analyst_done,
            on_resolver_done=_resolver_done,
        )

        if stop_at == 1:
            logger.debug("[DIRECTOR] Detenido en checkpoint 'analyst' (1/16)")
            return

        _step_start(f"📐  Planificando {num_beats} beats...")
        from src.application.services.story_analyst_service import StoryAnalystService

        analyst = self._analyst_service or StoryAnalystService(
            self.llm, self.prompt_builder, self.normalizer, self.debug_collector
        )

        plan_elapsed = 0.0
        logger.debug(f"[DIRECTOR] Anclajes extraídos → {num_beats} beats")

        if on_plan_ready is not None:
            on_plan_ready(num_beats, plan_elapsed)

        journal = initial_journal

        for beat_id in range(1, num_beats + 1):
            macro_beat, journal, llm_elapsed = await self._execute_single_beat(
                story=story,
                beat_id=beat_id,
                num_beats=num_beats,
                narrative_anchors=narrative_anchors,
                rule_distribution=rule_distribution,
                analyst=analyst,
                journal=journal,
                stop_at=stop_at,
                on_step_start=on_step_start,
            )
            yield macro_beat, journal, llm_elapsed

    async def _execute_single_beat(
        self,
        story: Story,
        beat_id: int,
        num_beats: int,
        narrative_anchors: dict,
        rule_distribution: dict,
        analyst,
        journal: NarrativeJournal | None,
        stop_at: int | None,
        on_step_start: Callable[[str], None] | None = None,
    ) -> tuple[MacroBeat, NarrativeJournal, float]:
        """Ejecuta una iteración completa de beat: MAPPER → VOZ → JOURNAL.

        Args:
            story: Historia.
            beat_id: Número del beat (1-based).
            num_beats: Total de beats.
            narrative_anchors: Anclajes del paso global.
            rule_distribution: Distribución de reglas/escenarios.
            analyst: Instancia de StoryAnalystService (para resolve_beat_anchors).
            journal: Journal del beat anterior (None para beat 1).
            stop_at: Checkpoint ordinal actual, None si no hay checkpoint.
            on_step_start: Callback para reporter.

        Returns:
            (macro_beat, journal_actualizado, llm_elapsed). Si stop_at indica
            detener en mapper/voz/journal, retorna con macro_beat.status=PENDING
            y elapsed=0.0.

        Raises:
            StopIteration: cuando stop_at indica que el loop debe terminar.
        """
        cp_mapper = ordinal(f"mapper:{beat_id}")
        cp_voz = ordinal(f"voz:{beat_id}")
        cp_journal = ordinal(f"journal:{beat_id}")

        beat_anchors = analyst.resolve_beat_anchors(narrative_anchors, beat_id)

        synopsis_slice = self.prompt_builder.get_beat_sinopsis_slice(
            story.sinopsis, beat_id, num_beats
        )
        dist = rule_distribution.get(str(beat_id), {})
        active_rules = dist.get("rules", [])
        s_idx = dist.get("scenario_index", 0)
        active_scenario_desc = ""
        if story.scenarios and 0 <= s_idx < len(story.scenarios):
            active_scenario_desc = story.scenarios[s_idx].name

        beat_info = self.prompt_builder.get_beat_info(beat_id)
        beat_type = beat_info.get("name", "")
        beat_intent = beat_info.get("intent", "")
        beat_intensity = beat_info.get("intensity", "")

        if on_step_start:
            on_step_start(f"📐  Mapeando beat {beat_id}/{num_beats}...")

        mapper = SynopsisBeatMapper(
            self.llm,
            self.prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
        )
        macro_beat = await mapper.map_one(
            story=story,
            macro_beat_id=beat_id,
            beat_anchors=beat_anchors,
            previous_journal=journal,
            synopsis_slice=synopsis_slice,
            active_rules=active_rules,
            active_scenario_description=active_scenario_desc,
            beat_intent=beat_intent,
            beat_type=beat_type,
            beat_intensity=beat_intensity,
            atmosphere=story.atmosfera,
        )

        if beat_type:
            try:
                macro_beat.beat_type = BeatType(beat_type)
            except ValueError:
                pass

        if stop_at == cp_mapper:
            macro_beat.status = BeatStatus.PENDING
            logger.debug(f"[DIRECTOR] Detenido en checkpoint 'mapper:{beat_id}' ({cp_mapper}/16)")
            return macro_beat, journal, 0.0

        macro_beat.active_rules = active_rules
        macro_beat.active_scenario_description = active_scenario_desc

        macro_beat.user_prompt = self.prompt_builder.build_narrative_context(
            macro_beat, beat_anchors, journal, story=story
        )

        voz = self._voz
        journalist = self._journalist

        if on_step_start:
            on_step_start(f"✍️   Narrando beat {beat_id}/{num_beats}...")
        macro_beat, llm_elapsed = await voz.narrate(macro_beat, story)

        if on_step_start:
            on_step_start(f"📓  Actualizando journal beat {beat_id}/{num_beats}...")
        journal = await journalist.extract(story, macro_beat, journal)

        if stop_at == cp_voz:
            macro_beat.status = BeatStatus.PENDING
            logger.debug(f"[DIRECTOR] Detenido en checkpoint 'voz:{beat_id}' ({cp_voz}/16)")
            return macro_beat, journal, llm_elapsed

        if stop_at == cp_journal:
            logger.debug(f"[DIRECTOR] Detenido en checkpoint 'journal:{beat_id}' ({cp_journal}/16)")
            return macro_beat, journal, llm_elapsed

        return macro_beat, journal, llm_elapsed

    async def execute_narration(
        self,
        story: Story,
        beats_to_narrate: list[Beat],
        initial_journal: NarrativeJournal | None = None,
    ) -> AsyncIterator[tuple[Beat, NarrativeJournal, float]]:
        """Narra una lista de beats pre-existentes.

        Yields (beat_completado, journal_actualizado, llm_elapsed) por cada beat.
        """
        voz = self._voz
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
