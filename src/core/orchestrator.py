"""Core Orchestrator - Orquesta el flujo completo de generación."""

from pathlib import Path

from src.application.dto import StoryCreateDTO
from src.application.services import PromptBuilder
from src.application.use_cases import (
    CreateStoryUseCase,
    DirectorUseCase,
    VozUseCase,
)
from src.cli.logger import logger
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, NarrativeJournal, Story
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository


class StoryRunner:
    """Orquestador del flujo completo de generación de historias."""

    def __init__(
        self,
        llm_adapter: LLMProvider,
        story_repo: SQLStoryRepository,
        beat_repo: SQLBeatRepository,
        prompt_builder: PromptBuilder,
        output_dir: Path,
    ):
        self.llm = llm_adapter
        self.story_repo = story_repo
        self.beat_repo = beat_repo
        self.prompt_builder = prompt_builder
        self.output_dir = output_dir

    async def run_full(
        self,
        title: str,
        protagonista: str,
        relator: str,
        escenarios: str,
        sinopsis: str,
        atmosfera: str,
        num_beats: int = 10,
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
        )
        story = await create_story.execute(dto)

        logger.info(
            f"[ORQUESTADOR] Historia creada en BD con ID: {story.id}", module="orchestrator", line=1
        )

        await self._run_plan(story, num_beats)

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

    async def _run_plan(self, story: Story, num_beats: int) -> list[Beat]:
        """Genera el plan de beats."""
        logger.info(f"[DIRECTOR] Planificando {num_beats} beats", module="orchestrator", line=1)

        create_plan = DirectorUseCase(self.llm, self.prompt_builder)
        plan = await create_plan.execute(story, num_beats=num_beats)

        for beat in plan.beats:
            await self.beat_repo.save(beat, story.id)

        logger.info(
            f"[DIRECTOR] Plan guardado: {len(plan.beats)} beats generados",
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

        for i, beat in enumerate(pending_beats):
            logger.info(
                f"[VOZ] Narrando Beat #{beat.number} ({i + 1}/{len(pending_beats)})",
                module="orchestrator",
                line=1,
            )

            generated_beat, journal = await narrate_beat.execute(
                story=story,
                beat=beat,
                previous_beats=completed_beats,
                journal=journal,
            )

            await self.beat_repo.save(generated_beat, story.id)
            if journal:
                await self.story_repo.save_journal(story.id, journal)
            completed_beats.append(generated_beat)

            logger.info(
                f"[VOZ] Beat #{beat.number} completado y guardado", module="orchestrator", line=1
            )

        logger.info(
            "[VOZ] Todos los beats han sido narrados con éxito", module="orchestrator", line=1
        )
