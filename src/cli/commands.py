"""CLI Commands for NarrativeForge."""

import time
from datetime import datetime
from pathlib import Path
from uuid import UUID

from src.application.services import PromptBuilder
from src.config import settings
from src.application.use_cases import (
    CreateStoryUseCase,
    DirectorUseCase,
    VozUseCase,
)
from src.cli.exceptions import (
    ExportError,
    GenerationError,
    OllamaConnectionError,
    StoryNotFoundError,
    ValidationError,
)
from src.cli.logger import logger
from src.cli.progress import ProgressReporter
from src.core.orchestrator import StoryRunner
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.infrastructure.renderers import MarkdownRenderer


def _write_markdown(story, output_dir: Path) -> Path:
    """Renderiza la historia a Markdown y la escribe en output_dir. Retorna la ruta."""
    renderer = MarkdownRenderer()
    output_dir.mkdir(parents=True, exist_ok=True)

    md_content = renderer.render(story)
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    safe_title = (
        "".join(c for c in story.title if c.isalnum() or c in (" ", "-", "_"))
        .strip()
        .replace(" ", "_")
        .lower()
    )
    output_path = output_dir / f"{safe_title}_{timestamp}.md"
    output_path.write_text(md_content, encoding="utf-8")
    return output_path


async def _init_database() -> None:
    """Initialize database if needed."""
    try:
        await init_db()
    except Exception as e:
        raise ValidationError(f"Error al inicializar la base de datos: {e}")


def generate(
    title: str,
    protagonista: str,
    relator: str,
    escenarios: str,
    sinopsis: str,
    atmosfera: str,
    use_mock: bool,
    output_dir: Path,
    input_file: str | None = None,
    provider: str | None = None,
    debug: bool = False,
) -> None:
    """Generate complete story with plan and narrated beats."""
    reglas: list[str] = []

    if input_file:
        from src.infrastructure.parsers import MarkdownStoryParser

        parser = MarkdownStoryParser()
        story_data = parser.parse(input_file)

        title = story_data.title
        protagonista = story_data.protagonista
        relator = story_data.relator
        escenarios = story_data.escenarios
        sinopsis = story_data.sinopsis
        atmosfera = story_data.atmosfera
        reglas = story_data.reglas

        logger.info(f"[COMANDOS] Cargando historia desde: {input_file}", module="commands", line=1)

    logger.info(f"[COMANDOS] Iniciando generación de historia: {title}", module="commands", line=1)

    try:
        import asyncio

        asyncio.run(
            _generate_async(
                title,
                protagonista,
                relator,
                escenarios,
                sinopsis,
                atmosfera,
                use_mock,
                output_dir,
                provider,
                reglas,
                debug=debug,
            )
        )
    except OllamaConnectionError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en la generación: {e}", module="commands", line=1)
        raise GenerationError(str(e))

    logger.info(f"[COMANDOS] Generación de historia completada: {title}", module="commands", line=1)


async def _generate_async(
    title: str,
    protagonista: str,
    relator: str,
    escenarios: str,
    sinopsis: str,
    atmosfera: str,
    use_mock: bool,
    output_dir: Path,
    provider: str | None = None,
    reglas: list[str] | None = None,
    debug: bool = False,
) -> None:
    """Async implementation of generate."""
    await _init_database()

    llm = LLMFactory.get_provider(use_mock=use_mock, provider=provider)
    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()
    prompt_builder = PromptBuilder()
    reporter = ProgressReporter()

    reporter.start(title)
    reporter.config_summary(
        model=settings.llm_model,
        director_t=settings.director_temperature,
        voz_t=settings.voz_temperature,
        journal_t=settings.state_extractor_temperature,
    )
    t_total = time.perf_counter()

    from src.application.services.debug_collector import DebugCollector, NullDebugCollector
    collector = DebugCollector() if debug else NullDebugCollector()

    runner = StoryRunner(
        llm_adapter=llm,
        story_repo=story_repo,
        beat_repo=beat_repo,
        prompt_builder=prompt_builder,
        output_dir=output_dir,
        reporter=reporter,
        debug_collector=collector,
    )

    story = await runner.run_full(
        title=title,
        protagonista=protagonista,
        relator=relator,
        escenarios=escenarios,
        sinopsis=sinopsis,
        atmosfera=atmosfera,
        reglas=reglas or [],
    )

    t_export = time.perf_counter()
    output_path = _write_markdown(story, output_dir)
    reporter.export_done(time.perf_counter() - t_export)

    reporter.done(time.perf_counter() - t_total, output_path)
    logger.info(f"[COMANDOS] Historia exportada a: {output_path}", module="commands", line=1)


def plan(
    title: str,
    use_mock: bool,
    output_dir: Path,
    provider: str | None = None,
) -> None:
    """Generate only the story plan (beats)."""
    logger.info(f"[COMANDOS] Iniciando generación de plan: {title}", module="commands", line=1)

    try:
        import asyncio

        asyncio.run(_plan_async(title, use_mock, output_dir, provider))
    except Exception as e:
        logger.error(f"[COMANDOS] Error al generar el plan: {e}", module="commands", line=1)
        raise GenerationError(str(e))

    logger.info(f"[COMANDOS] Generación de plan completada: {title}", module="commands", line=1)


async def _plan_async(
    title: str,
    use_mock: bool,
    output_dir: Path,  # noqa: ARG001
    provider: str | None = None,
) -> None:
    """Async implementation of plan."""
    await _init_database()

    llm = LLMFactory.get_provider(use_mock=use_mock, provider=provider)
    story_repo = SQLStoryRepository()
    prompt_builder = PromptBuilder()

    create_story = CreateStoryUseCase(story_repo)
    create_plan = DirectorUseCase(llm, prompt_builder)

    story = await create_story.execute(
        title=title,
        protagonista="",
        relator="tercera_persona",
        escenarios="",
        sinopsis="",
        atmosfera="",
    )

    plan = await create_plan.execute(story)
    logger.info(f"[COMANDOS] Se han generado {len(plan.beats)} beats", module="commands", line=1)


def narrate(
    story_id: str,
    beats: str,
    use_mock: bool,
    provider: str | None = None,
) -> None:
    """Narrate specific beats from an existing story."""
    logger.info(
        f"[COMANDOS] Iniciando narración para historia: {story_id}", module="commands", line=1
    )

    try:
        import asyncio

        asyncio.run(_narrate_async(story_id, beats, use_mock, provider))
    except StoryNotFoundError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en la narración: {e}", module="commands", line=1)
        raise GenerationError(str(e))

    logger.info(
        f"[COMANDOS] Narración completada para historia: {story_id}", module="commands", line=1
    )


async def _narrate_async(
    story_id: str,
    beats_csv: str,
    use_mock: bool,
    provider: str | None = None,
) -> None:
    """Async implementation of narrate."""
    await _init_database()

    try:
        story_uuid = UUID(story_id)
    except ValueError:
        raise ValidationError(f"Formato de UUID inválido: {story_id}")

    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()

    story = await story_repo.get_by_id(story_uuid)
    if not story:
        raise StoryNotFoundError(story_id)

    beat_list = [int(b.strip()) for b in beats_csv.split(",") if b.strip().isdigit()]
    if not beat_list:
        raise ValidationError(f"Formato de beats inválido: {beats_csv}")

    all_beats = await beat_repo.get_by_story(story_uuid)
    beats_to_narrate = [b for b in all_beats if b.number in beat_list]

    if not beats_to_narrate:
        raise ValidationError("No se encontraron beats que coincidan con la selección")

    llm = LLMFactory.get_provider(use_mock=use_mock, provider=provider)
    narrate_beat = VozUseCase(llm)

    for beat in beats_to_narrate:
        logger.info(f"[COMANDOS] Narrando beat #{beat.number}", module="commands", line=1)
        generated_beat, _, _ = await narrate_beat.execute(story, beat)
        await beat_repo.save(generated_beat, story_uuid)
        logger.info(f"[COMANDOS] Beat #{beat.number} completado", module="commands", line=1)


def generate_from_db(
    story_id: str,
    use_mock: bool,
    output_dir: Path,
    provider: str | None = None,
    debug: bool = False,
) -> None:
    """Generate story from existing DB entry."""
    logger.info(
        f"[COMANDOS] Iniciando generación desde BD para historia: {story_id}",
        module="commands",
        line=1,
    )

    try:
        import asyncio

        asyncio.run(_generate_from_db_async(story_id, use_mock, output_dir, provider, debug=debug))
    except StoryNotFoundError:
        raise
    except OllamaConnectionError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en la generación desde BD: {e}", module="commands", line=1)
        raise GenerationError(str(e))

    logger.info(f"[COMANDOS] Generación desde BD completada: {story_id}", module="commands", line=1)


async def _generate_from_db_async(
    story_id: str,
    use_mock: bool,
    output_dir: Path,
    provider: str | None = None,
    debug: bool = False,
) -> None:
    """Async implementation of generate_from_db."""
    await _init_database()

    story_repo = SQLStoryRepository()
    story = await story_repo.get_by_string_id(story_id)

    if not story:
        raise StoryNotFoundError(story_id)

    llm = LLMFactory.get_provider(use_mock=use_mock, provider=provider)
    beat_repo = SQLBeatRepository()
    prompt_builder = PromptBuilder()
    reporter = ProgressReporter()

    reporter.start(story.title)
    t_total = time.perf_counter()

    from src.application.services.debug_collector import DebugCollector, NullDebugCollector
    collector = DebugCollector() if debug else NullDebugCollector()

    runner = StoryRunner(
        llm_adapter=llm,
        story_repo=story_repo,
        beat_repo=beat_repo,
        prompt_builder=prompt_builder,
        output_dir=output_dir,
        reporter=reporter,
        debug_collector=collector,
    )

    story = await runner.run_from_story(story)

    t_export = time.perf_counter()
    output_path = _write_markdown(story, output_dir)
    reporter.export_done(time.perf_counter() - t_export)

    reporter.done(time.perf_counter() - t_total, output_path)
    logger.info(f"[COMANDOS] Historia exportada a: {output_path}", module="commands", line=1)


def export_(
    story_id: str,
    format: str,
    output_dir: Path,
    provider: str | None = None,  # noqa: ARG001
) -> None:
    """Export story to file."""
    logger.info(
        f"[COMANDOS] Iniciando exportación para historia: {story_id}", module="commands", line=1
    )

    try:
        import asyncio

        asyncio.run(_export_async(story_id, format, output_dir))
    except StoryNotFoundError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en la exportación: {e}", module="commands", line=1)
        raise ExportError(str(e))

    logger.info(
        f"[COMANDOS] Exportación completada para historia: {story_id}", module="commands", line=1
    )


async def _export_async(
    story_id: str,
    format: str,  # noqa: ARG001
    output_dir: Path,
) -> None:
    """Async implementation of export."""
    await _init_database()

    try:
        story_uuid = UUID(story_id)
    except ValueError:
        raise ValidationError(f"Formato de UUID inválido: {story_id}")

    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()

    story = await story_repo.get_by_id(story_uuid)
    if not story:
        raise StoryNotFoundError(story_id)

    beats = await beat_repo.get_by_story(story_uuid)

    story.beats = beats
    output_path = _write_markdown(story, output_dir)
    logger.info(f"[COMANDOS] Historia exportada a: {output_path}", module="commands", line=1)
