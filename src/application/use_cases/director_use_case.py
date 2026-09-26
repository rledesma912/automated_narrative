"""DirectorUseCase - orquestador de la generación de un relato (Spec-530 S7).

Un solo camino: el relato sale de la escaleta. Si la historia no la tiene (p. ej.
entró por `import-yaml`), primero se arma (Planificador + Verificador) y se guarda;
después cada acto es Voz + memoria.
"""

import logging
from collections.abc import AsyncIterator
from typing import Callable

from src.application.services import PromptBuilder
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.use_cases.voz_use_case import VozUseCase
from src.domain.interfaces import LLMProvider
from src.domain.jobs import JobStage
from src.domain.models import BeatType, MacroBeat, NarrativeJournal, Story
from src.infrastructure.normalizers import ResponseNormalizer

logger = logging.getLogger(__name__)


class DirectorUseCase:
    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        normalizer: ResponseNormalizer | None = None,
        debug_collector: DebugCollector | None = None,
        voz: VozUseCase | None = None,
        story_repo=None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()
        self.story_repo = story_repo
        self._voz = voz or VozUseCase(
            llm,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
        )

    async def execute_full(
        self,
        story: Story,
        initial_journal: NarrativeJournal | None = None,
        on_plan_ready: Callable[[int, float], None] | None = None,
        on_step_start: Callable[[str], None] | None = None,
        on_stage: Callable[[JobStage, int | None], None] | None = None,
    ) -> AsyncIterator[tuple[MacroBeat, NarrativeJournal, float]]:
        """Arma la escaleta si falta y narra acto por acto.

        Yields (acto narrado, memoria actualizada, segundos de la Voz) por acto.
        """
        # Import local: los servicios del asistente importan el paquete `application`.
        from src.application.services.authoring.outline_narrator import OutlineNarrator

        if len(story.outline) != self.prompt_builder.num_beats:
            await self._plan(story, on_stage, on_step_start)

        narrator = OutlineNarrator(self.llm, self.prompt_builder)
        acts = sorted(story.outline, key=lambda a: a.number)
        if on_plan_ready is not None:
            on_plan_ready(len(acts), 0.0)
        journal = initial_journal
        # La sinopsis del acto que escribió el autor se conserva (la lee el export YAML).
        synopsis = {b.number: b.synopsis_beat for b in story.beats if b.synopsis_beat}
        for act in acts:
            info = self.prompt_builder.get_beat_info(act.number)
            bullets = "\n".join(f"- {e}" for e in act.events)
            macro_beat = MacroBeat(
                number=act.number,
                summary=bullets,
                synopsis_beat=synopsis.get(act.number, bullets),
                active_scenario_description=act.scenario,
            )
            try:
                macro_beat.beat_type = BeatType(info.get("name", ""))
            except ValueError:
                pass
            system_prompt, user_prompt = narrator.voice_prompts(story, act, journal)

            if on_stage:
                on_stage(JobStage.VOZ, act.number)
            if on_step_start:
                on_step_start(f"✍️   Narrando acto {act.number}/{len(acts)}...")
            macro_beat, llm_elapsed = await self._voz.narrate_with_prompts(
                macro_beat, system_prompt, user_prompt
            )

            if on_stage:
                on_stage(JobStage.JOURNAL, act.number)
            if on_step_start:
                on_step_start(f"📓  Memoria del acto {act.number}/{len(acts)}...")
            journal = await narrator.remember(story, act, macro_beat.generated_act, journal)
            yield macro_beat, journal, llm_elapsed

    async def _plan(
        self,
        story: Story,
        on_stage: Callable[[JobStage, int | None], None] | None,
        on_step_start: Callable[[str], None] | None,
    ) -> None:
        """La historia no tiene escaleta: se arma y se revisa antes de narrar."""
        from src.application.services.authoring.planner import OutlinePlanner
        from src.application.services.authoring.verifier import OutlineVerifier

        if on_stage:
            on_stage(JobStage.PLANIFICADOR, None)
        if on_step_start:
            on_step_start("📐  Armando la escaleta...")
        acts, _ = await OutlinePlanner(self.llm, prompt_builder=self.prompt_builder).plan(story)
        if on_stage:
            on_stage(JobStage.VERIFICADOR, None)
        if on_step_start:
            on_step_start("🔎  Revisando la escaleta...")
        checked = await OutlineVerifier(self.llm).verify(story, acts)
        story.outline = checked.outline
        if self.story_repo is not None:
            await self.story_repo.save_outline(story.id, checked.outline)
        logger.info("[DIRECTOR] Escaleta armada para «%s» (%d actos)", story.title, len(acts))
