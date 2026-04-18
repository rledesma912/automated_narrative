"""Core Orchestrator - Orquesta el flujo completo de generación."""

import time
from pathlib import Path
from typing import TYPE_CHECKING

from src.application.dto import StoryCreateDTO
from src.application.services import PromptBuilder
from src.application.use_cases import (
    CreateStoryUseCase,
    DirectorUseCase,
    VozUseCase,
)
from src.cli.logger import logger
from src.cli.progress import SilentReporter
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, NarrativeJournal, Story
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository

if TYPE_CHECKING:
    from src.cli.progress import ProgressReporter


class StoryRunner:
    """Orquestador del flujo completo de generación de historias."""

    def __init__(
        self,
        llm_adapter: LLMProvider,
        story_repo: SQLStoryRepository,
        beat_repo: SQLBeatRepository,
        prompt_builder: PromptBuilder,
        output_dir: Path,
        reporter: "ProgressReporter | SilentReporter | None" = None,
    ):
        self.llm = llm_adapter
        self.story_repo = story_repo
        self.beat_repo = beat_repo
        self.prompt_builder = prompt_builder
        self.output_dir = output_dir
        self.reporter = reporter or SilentReporter()

    async def run_full(
        self,
        title: str,
        protagonista: str,
        relator: str,
        escenarios: str,
        sinopsis: str,
        atmosfera: str,
        reglas: list[str] | None = None,
    ) -> Story:
        """Ejecuta el flujo completo: crear story + plan + narrar todos los beats."""
        logger.info(
            f"[ORQUESTADOR] Iniciando generación completa: {title}", module="orchestrator", line=1
        )

        create_story = CreateStoryUseCase(self.story_repo)
        dto = StoryCreateDTO(
            title=title,
            protagonista=protagonista,
            relator=relator,
            escenarios=escenarios,
            sinopsis=sinopsis,
            atmosfera=atmosfera,
            reglas=reglas or [],
        )
        story = await create_story.execute(dto)

        logger.info(
            f"[ORQUESTADOR] Historia creada en BD con ID: {story.id}", module="orchestrator", line=1
        )

        await self._run_plan(story)

        await self._run_narrate_all(story)

        logger.info(
            f"[ORQUESTADOR] Proceso finalizado con éxito: {title}", module="orchestrator", line=1
        )

        return story

    async def run_from_story(self, story: Story) -> Story:
        """Ejecuta la narración de beats existentes en DB (no genera nuevo plan)."""
        logger.info(
            f"[ORQUESTADOR] Iniciando desde historia existente: {story.title}",
            module="orchestrator",
            line=1,
        )

        await self._run_narrate_all(story)

        logger.info(
            f"[ORQUESTADOR] Narración finalizada para: {story.title}", module="orchestrator", line=1
        )

        return story

    async def _run_plan(self, story: Story) -> list[Beat]:
        """Genera el plan de beats. La cantidad viene del YAML via PromptBuilder."""
        create_plan = DirectorUseCase(self.llm, self.prompt_builder)
        t0 = time.perf_counter()
        plan = await create_plan.execute(story)
        elapsed = time.perf_counter() - t0

        for beat in plan.beats:
            await self.beat_repo.save(beat, story.id)

        num_beats = len(plan.beats)
        self.reporter.plan_done(num_beats, elapsed)
        logger.info(
            f"[DIRECTOR] Plan guardado: {num_beats} beats generados",
            module="orchestrator",
            line=1,
        )

        return plan.beats

    async def _run_narrate_all(self, story: Story) -> list[Beat]:
        """Narra todos los beats pendientes."""
        logger.info("[VOZ] Iniciando narración de beats pendientes", module="orchestrator", line=1)

        beats = await self.beat_repo.get_by_story(story.id)
        pending_beats = [b for b in beats if b.status != "completed"]

        if not pending_beats:
            logger.info("[VOZ] No hay beats pendientes por narrar", module="orchestrator", line=1)
            return beats

        narrate_beat = VozUseCase(self.llm)
        completed_beats = []
        journal: NarrativeJournal | None = await self.story_repo.get_journal(story.id)
        total = len(pending_beats)

        for i, beat in enumerate(pending_beats):
            logger.info(
                f"[VOZ] Narrando Beat #{beat.number} ({i + 1}/{total})",
                module="orchestrator",
                line=1,
            )

            t0 = time.perf_counter()
            generated_beat, journal, llm_elapsed = await narrate_beat.execute(
                story=story,
                beat=beat,
                previous_beats=completed_beats,
                journal=journal,
            )
            step_elapsed = time.perf_counter() - t0

            await self.beat_repo.save(generated_beat, story.id)
            if journal:
                await self.story_repo.save_journal(story.id, journal)
            completed_beats.append(generated_beat)

            self.reporter.beat_done(i + 1, total, step_elapsed, llm_elapsed)
            logger.info(
                f"[VOZ] Beat #{beat.number} completado y guardado", module="orchestrator", line=1
            )

        story.beats = completed_beats

        logger.info(
            "[VOZ] Todos los beats han sido narrados con éxito", module="orchestrator", line=1
        )
