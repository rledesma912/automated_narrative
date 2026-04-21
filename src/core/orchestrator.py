"""Core Orchestrator - thin shell de infraestructura."""

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from src.application.dto import StoryCreateDTO
from src.application.services import PromptBuilder
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.use_cases import CreateStoryUseCase, DirectorUseCase
from src.cli.logger import logger
from src.cli.progress import SilentReporter
from src.domain.interfaces import LLMProvider
from src.domain.models import Story
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.normalizers import ResponseNormalizer

if TYPE_CHECKING:
    from src.cli.progress import ProgressReporter


class StoryRunner:
    """Shell de infraestructura: persiste, reporta y delega generación al Director."""

    def __init__(
        self,
        llm_adapter: LLMProvider,
        story_repo: SQLStoryRepository,
        beat_repo: SQLBeatRepository,
        prompt_builder: PromptBuilder,
        output_dir: Path,
        reporter: "ProgressReporter | SilentReporter | None" = None,
        debug_collector: DebugCollector | None = None,
    ):
        self.llm = llm_adapter
        self.story_repo = story_repo
        self.beat_repo = beat_repo
        self.prompt_builder = prompt_builder
        self.output_dir = output_dir
        self.reporter = reporter or SilentReporter()
        self.normalizer = ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()

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
        """Flujo completo: crear story + plan + narrar todos los beats."""
        from src.config import settings as cfg

        logger.info("[SESSION] ── Iniciando generación ──────────────────────────────", module="orchestrator", line=1)
        logger.info(
            f"[SESSION] title={title!r} profile={cfg.active_profile_name} "
            f"provider={cfg.llm_provider} "
            f"director={cfg.role_config('director').get('model')} "
            f"voz={cfg.role_config('voz').get('model')}",
            module="orchestrator", line=1,
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
        logger.info(f"[ORQUESTADOR] Historia creada en BD con ID: {story.id}", module="orchestrator", line=1)

        director = DirectorUseCase(
            self.llm,
            self.prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
        )

        completed = []
        total = self.prompt_builder.num_beats
        beat_t0 = perf_counter()

        async for beat, journal, llm_elapsed in director.execute_full(
            story,
            on_plan_ready=lambda n, t: self.reporter.plan_done(n, t),
        ):
            await self.beat_repo.save(beat, story.id)
            await self.story_repo.save_journal(story.id, journal)
            step_elapsed = perf_counter() - beat_t0
            self.reporter.beat_done(len(completed) + 1, total, step_elapsed, llm_elapsed)
            completed.append(beat)
            logger.info(f"[VOZ] Beat #{beat.number} completado y guardado", module="orchestrator", line=1)
            beat_t0 = perf_counter()

        story.beats = completed

        if story.narrative_brief:
            await self.story_repo.save_narrative_brief(story.id, story.narrative_brief)

        if self.debug_collector.is_active():
            story_meta = {
                "profile": cfg.active_profile_name,
                "provider": cfg.llm_provider,
                "story_id": str(story.id),
                "title": title,
                "protagonista": protagonista,
                "sinopsis": sinopsis,
                "atmosfera": atmosfera,
                "relator": relator,
            }
            try:
                debug_path = self.debug_collector.write(self.output_dir, story_meta)
                logger.info(f"[DEBUG] Archivo de diagnóstico generado: {debug_path}", module="orchestrator", line=1)
            except Exception as exc:
                logger.warning(f"[DEBUG] No se pudo escribir el archivo de diagnóstico: {exc}", module="orchestrator", line=1)

        logger.info(f"[SESSION] ── Generación completa: {title!r} ──────────────────", module="orchestrator", line=1)
        return story

    async def run_from_story(self, story: Story) -> Story:
        """Narra beats pendientes de una historia ya existente en DB."""
        logger.info(f"[ORQUESTADOR] Iniciando desde historia existente: {story.title}", module="orchestrator", line=1)

        all_beats = await self.beat_repo.get_by_story(story.id)
        pending_beats = [b for b in all_beats if b.status != "completed"]

        if not pending_beats:
            logger.info("[VOZ] No hay beats pendientes por narrar", module="orchestrator", line=1)
            story.beats = [b for b in all_beats if b.status == "completed"]
            return story

        journal = await self.story_repo.get_journal(story.id)

        director = DirectorUseCase(
            self.llm,
            self.prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
        )

        completed = []
        total = len(pending_beats)
        beat_t0 = perf_counter()

        async for beat, journal, llm_elapsed in director.execute_narration(
            story, pending_beats, initial_journal=journal
        ):
            await self.beat_repo.save(beat, story.id)
            await self.story_repo.save_journal(story.id, journal)
            step_elapsed = perf_counter() - beat_t0
            self.reporter.beat_done(len(completed) + 1, total, step_elapsed, llm_elapsed)
            completed.append(beat)
            logger.info(f"[VOZ] Beat #{beat.number} completado y guardado", module="orchestrator", line=1)
            beat_t0 = perf_counter()

        story.beats = completed
        logger.info(f"[ORQUESTADOR] Narración finalizada para: {story.title}", module="orchestrator", line=1)
        return story
