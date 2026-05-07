"""Core Orchestrator - thin shell de infraestructura."""

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from src.application.dto import StoryCreateDTO
from src.application.services import PromptBuilder
from src.application.services.checkpoint import ordinal, validate
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.use_cases import CreateStoryUseCase, DirectorUseCase
from src.cli.logger import logger
from src.cli.progress import SilentReporter
from src.domain.interfaces import LLMProvider
from src.domain.models import BeatStatus, Story
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.normalizers import ResponseNormalizer

if TYPE_CHECKING:
    from src.application.use_cases.generate_narratives_use_case import (
        GenerateNarrativesUseCase,
    )
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
        narrative_use_case: "GenerateNarrativesUseCase | None" = None,
    ):
        self.llm = llm_adapter
        self.story_repo = story_repo
        self.beat_repo = beat_repo
        self.prompt_builder = prompt_builder
        self.output_dir = output_dir
        self.reporter = reporter or SilentReporter()
        self.normalizer = ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()
        self.narrative_use_case = narrative_use_case
        self.last_narrative_id: str | None = None

    async def run_full(
        self,
        title: str,
        protagonista: str,
        relator: str,
        escenarios: list[str] | str,
        sinopsis: str,
        atmosfera: str,
        reglas: list[str] | None = None,
        stop_after: str | None = None,
        storyteller_config: dict | None = None,
        typed_rules: list[dict] | None = None,
        personajes_full: list[dict] | None = None,
    ) -> Story:
        """Flujo completo: crear story + plan + narrar todos los beats.

        Args:
            stop_after: Checkpoint para detener el pipeline (Spec-040).
                Valores: analyst, mapper:1..5, voz:1..5, journal:1..5.
        """
        if stop_after is not None:
            validate(stop_after)
        from src.config import settings as cfg

        logger.info("[SESSION] ── Iniciando generación ──────────────────────────────")
        logger.info(
            f"[SESSION] title={title!r} profile={cfg.active_profile_name} "
            f"provider={cfg.llm_provider} "
            f"director={cfg.role_config('director').get('model')} "
            f"voz={cfg.role_config('voz').get('model')}"
        )

        create_story = CreateStoryUseCase(self.story_repo)
        escenarios_list = (
            escenarios
            if isinstance(escenarios, list)
            else ([e.strip() for e in escenarios.split("/") if e.strip()] if escenarios else [])
        )
        dto = StoryCreateDTO(
            title=title,
            protagonista=protagonista,
            relator=relator,
            escenarios=escenarios_list,
            sinopsis=sinopsis,
            atmosfera=atmosfera,
            reglas=reglas or [],
            storyteller_config=storyteller_config,
            typed_rules=typed_rules or [],
            personajes_full=personajes_full or [],
        )
        story = await create_story.execute(dto)
        logger.info(f"[ORQUESTADOR] Historia creada en BD con ID: {story.id}")

        director = DirectorUseCase(
            self.llm,
            self.prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
            story_repo=self.story_repo,
        )

        completed = []
        total = self.prompt_builder.num_beats
        beat_t0 = perf_counter()

        async for beat, journal, llm_elapsed in director.execute_full(
            story,
            on_plan_ready=lambda n, t: self.reporter.plan_done(n, t),
            on_step_done=lambda label, t: self.reporter.step_done(label, t),
            on_step_start=lambda msg: self.reporter.step_start(msg),
            stop_after=stop_after,
        ):
            self.reporter.step_start(f"Guardando beat {beat.number}/{total}...")
            await self.beat_repo.save(beat, story.id)
            if journal is not None:
                await self.story_repo.save_journal(story.id, journal, beat.number)
            step_elapsed = perf_counter() - beat_t0
            self.reporter.beat_done(len(completed) + 1, total, step_elapsed, llm_elapsed)
            completed.append(beat)
            logger.info(f"[VOZ] Beat #{beat.number} completado y guardado")
            beat_t0 = perf_counter()

        if stop_after is not None:
            cp_ordinal = ordinal(stop_after)
            debug_path = (
                str(Path(cfg.output_dir) / f"debug_{title}_{cp_ordinal}.md")
                if self.debug_collector.is_active()
                else None
            )
            self.reporter.checkpoint_pause(stop_after, str(story.id), cp_ordinal, debug_path)

        story.beats = completed

        if stop_after is None and self.narrative_use_case is not None:
            await self._consolidate_narrative(story)

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
                logger.info(f"[DEBUG] Archivo de diagnóstico generado: {debug_path}")
            except Exception as exc:
                logger.warning(f"[DEBUG] No se pudo escribir el archivo de diagnóstico: {exc}")

        logger.info(f"[SESSION] ── Generación completa: {title!r} ──────────────────")
        return story

    async def run_from_story(self, story: Story) -> Story:
        """Narra beats pendientes de una historia ya existente en DB."""
        logger.info(f"[ORQUESTADOR] Iniciando desde historia existente: {story.title}")

        all_beats = await self.beat_repo.get_by_story(story.id)
        pending_beats = [b for b in all_beats if b.status != BeatStatus.COMPLETED]

        if not pending_beats:
            logger.info("[VOZ] No hay beats pendientes por narrar")
            story.beats = [b for b in all_beats if b.status == BeatStatus.COMPLETED]
            return story

        journal = await self.story_repo.get_journal(story.id)

        director = DirectorUseCase(
            self.llm,
            self.prompt_builder,
            normalizer=self.normalizer,
            debug_collector=self.debug_collector,
            story_repo=self.story_repo,
        )

        completed = []
        total = len(pending_beats)
        beat_t0 = perf_counter()

        async for beat, latest_journal, llm_elapsed in director.execute_narration(
            story, pending_beats, initial_journal=journal
        ):
            await self.beat_repo.save(beat, story.id)
            await self.story_repo.save_journal(story.id, latest_journal, beat.number)
            step_elapsed = perf_counter() - beat_t0
            self.reporter.beat_done(len(completed) + 1, total, step_elapsed, llm_elapsed)
            completed.append(beat)
            logger.info(f"[VOZ] Beat #{beat.number} completado y guardado")
            beat_t0 = perf_counter()

        full_beats = await self.beat_repo.get_by_story(story.id)
        all_completed = full_beats and all(b.status == BeatStatus.COMPLETED for b in full_beats)
        if all_completed and self.narrative_use_case is not None:
            story.beats = full_beats
            await self._consolidate_narrative(story)
        else:
            story.beats = completed

        logger.info(f"[ORQUESTADOR] Narración finalizada para: {story.title}")
        return story

    async def _consolidate_narrative(self, story: Story) -> None:
        """Consolida los beats narrados en `generated_narrative` (Spec-312)."""
        try:
            narrative = await self.narrative_use_case.consolidate_and_save(story)
            self.last_narrative_id = str(narrative.id)
            logger.info(f"[NARRATIVE] Variante persistida: {narrative.id}")
        except Exception as exc:
            logger.warning(f"[NARRATIVE] Fallo consolidación: {exc}")
