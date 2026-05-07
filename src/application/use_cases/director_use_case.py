"""DirectorUseCase - orquestador LLM punta a punta."""

import logging
from collections.abc import AsyncIterator
from time import perf_counter
from typing import TYPE_CHECKING, Callable

from src.application.services import MemoryJournalist, PromptBuilder
from src.application.services.checkpoint import VALID_CHECKPOINTS, ordinal
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.use_cases.synopsis_beat_mapper import SynopsisBeatMapper
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import (
    Beat,
    BeatStatus,
    BeatType,
    MacroBeat,
    NarrativeJournal,
    Story,
    StoryPlan,
)
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
        story_repo=None,
    ):
        from src.application.use_cases.voz_use_case import VozUseCase

        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()
        self.story_repo = story_repo

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

    async def _analyze_story(self, story: Story) -> str:
        """Fase 0: expande la sinopsis en un narrative brief estructurado."""
        role_cfg = settings.role_config("story_analyst")
        model = role_cfg.get("model", "mistral:latest")
        temperature = role_cfg.get("temperature", 0.3)

        prompt = self.prompt_builder.build_story_analyst_prompt(story)
        system_prompt = self.prompt_builder.build_story_analyst_system()
        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            role="story_analyst",
        )

        brief = self.normalizer.normalize(response.text, model_name=model).strip()

        variant = self.prompt_builder.get_variant_name()
        self.debug_collector.record(
            role="story_analyst",
            beat_number=None,
            source_component=DebugCollector.source_label(self),
            model=model,
            temperature=temperature,
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
            system_prompt=system_prompt,
            user_prompt=prompt,
            raw_response=response.text,
            normalized_response=brief,
            parser_result="n/a",
            elapsed_s=response.elapsed_s,
            system_prompt_file="story_analyst_system_compact.md" if variant == "compact" else "n/a",
            user_prompt_file="story_analyst_compact.md"
            if variant == "compact"
            else "story_analyst.md",
        )

        story.narrative_brief = brief
        logger.debug(f"[DIRECTOR] Narrative brief generado: {len(brief)} chars")
        return brief

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

        brief = await self._analyze_story(story)
        beats = await mapper.map(story, narrative_brief=brief)
        logger.debug(f"[DIRECTOR] Plan generado: {len(beats)} beats")

        return StoryPlan(story_id=story.id, title=story.title, beats=beats)

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
        from src.application.services.rule_scenario_resolver_service import (
            RuleScenarioResolverService,
        )
        from src.application.services.story_analyst_service import StoryAnalystService

        stop_at: int | None = VALID_CHECKPOINTS.get(stop_after) if stop_after else None
        t0 = perf_counter()

        analyst = StoryAnalystService(
            self.llm, self.prompt_builder, self.normalizer, self.debug_collector
        )

        if on_step_start:
            on_step_start("🔍  Analizando sinopsis y anclajes...")
        t_step = perf_counter()
        narrative_anchors = await analyst.extract_anchors(story)

        if self.story_repo is not None:
            await self.story_repo.save_narrative_anchors(story.id, narrative_anchors)

        if on_step_done:
            on_step_done("🔍  Analizando sinopsis y anclajes", perf_counter() - t_step)

        if stop_at == 1:
            logger.debug("[DIRECTOR] Detenido en checkpoint 'analyst' (1/16)")
            return

        resolver = RuleScenarioResolverService(
            self.llm, self.prompt_builder, self.normalizer, self.debug_collector
        )

        if on_step_start:
            on_step_start("⚖️   Distribuyendo reglas y escenarios...")
        t_step = perf_counter()
        rule_distribution = await resolver.resolve_distribution(story, anchors=narrative_anchors)
        if on_step_done:
            on_step_done("⚖️   Distribuyendo reglas y escenarios", perf_counter() - t_step)

        mapper = SynopsisBeatMapper(
            self.llm,
            self.prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
        )
        voz = self._voz
        journalist = self._journalist

        num_beats = self.prompt_builder.num_beats
        plan_elapsed = perf_counter() - t0
        logger.debug(f"[DIRECTOR] Anclajes extraídos en {plan_elapsed:.1f}s → {num_beats} beats")

        if on_plan_ready is not None:
            on_plan_ready(num_beats, plan_elapsed)

        journal = initial_journal
        num_beats = self.prompt_builder.num_beats

        for beat_id in range(1, num_beats + 1):
            cp_mapper = ordinal(f"mapper:{beat_id}")
            cp_voz = ordinal(f"voz:{beat_id}")
            cp_journal = ordinal(f"journal:{beat_id}")

            beat_anchors = analyst.resolve_beat_anchors(narrative_anchors, beat_id)

            # Segmentación de sinopsis y datos específicos del beat
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

            # Persistir tipo de beat desde YAML (YAML inicializa, DB gobierna — Spec-043)
            if beat_type:
                try:
                    macro_beat.beat_type = BeatType(beat_type)
                except ValueError:
                    pass

            if stop_at == cp_mapper:
                macro_beat.status = BeatStatus.PENDING
                logger.debug(
                    f"[DIRECTOR] Detenido en checkpoint 'mapper:{beat_id}' ({cp_mapper}/16)"
                )
                yield macro_beat, journal, 0.0
                return

            # Ya vienen asignados desde mapper.map_one, pero reforzamos por si acaso
            macro_beat.active_rules = active_rules
            macro_beat.active_scenario_description = active_scenario_desc

            macro_beat.narrative_context = self.prompt_builder.build_narrative_context(
                macro_beat, beat_anchors, journal, story=story
            )

            if on_step_start:
                on_step_start(f"✍️   Narrando beat {beat_id}/{num_beats}...")
            macro_beat, llm_elapsed = await voz.narrate(macro_beat, story)

            if on_step_start:
                on_step_start(f"📓  Actualizando journal beat {beat_id}/{num_beats}...")
            journal = await journalist.extract(story, macro_beat, journal)

            if stop_at == cp_voz:
                macro_beat.status = BeatStatus.PENDING
                logger.debug(f"[DIRECTOR] Detenido en checkpoint 'voz:{beat_id}' ({cp_voz}/16)")
                yield macro_beat, journal, llm_elapsed
                return

            if stop_at == cp_journal:
                logger.debug(
                    f"[DIRECTOR] Detenido en checkpoint 'journal:{beat_id}' ({cp_journal}/16)"
                )
                yield macro_beat, journal, llm_elapsed
                return

            yield macro_beat, journal, llm_elapsed

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
