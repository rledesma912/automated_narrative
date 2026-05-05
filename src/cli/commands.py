"""CLI Commands for NarrativeForge."""

import time
from pathlib import Path
from uuid import UUID

from src.cli.exceptions import (
    ExportError,
    GenerationError,
    OllamaConnectionError,
    StoryNotFoundError,
    ValidationError,
)
from src.cli.logger import logger
from src.config import settings
from src.domain.models import StoryStatus
from src.infrastructure.container import CLIContainer
from src.infrastructure.database.connection import init_db
from src.utils.timezone import now_argentina


def _write_markdown(story, output_dir: Path, renderer) -> Path:
    """Renderiza la historia a Markdown y la escribe en output_dir. Retorna la ruta."""
    output_dir.mkdir(parents=True, exist_ok=True)

    md_content = renderer.render(story)
    timestamp = now_argentina().strftime("%Y%m%d%H%M")
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
    hasta: str | None = None,
) -> None:
    """Generate complete story with plan and narrated beats.

    Args:
        hasta: Checkpoint para detener el pipeline (Spec-040).
            Valores: analyst, mapper:1..5, voz:1..5, journal:1..5.
    """
    reglas: list[str] = []
    storyteller_config: dict | None = None
    typed_rules: list[dict] = []
    personajes_full: list[dict] = []

    logger.info(f"[COMANDOS] Iniciando generación de historia: {title}")

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
                hasta=hasta,
                storyteller_config=storyteller_config,
                typed_rules=typed_rules,
                personajes_full=personajes_full,
                input_file=input_file,
            )
        )
    except OllamaConnectionError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en la generación: {e}")
        raise GenerationError(str(e)) from e

    logger.info(f"[COMANDOS] Generación de historia completada: {title}")


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
    hasta: str | None = None,
    storyteller_config: dict | None = None,
    typed_rules: list[dict] | None = None,
    personajes_full: list[dict] | None = None,
    input_file: str | None = None,
) -> None:
    """Async implementation of generate."""
    await _init_database()

    if input_file:
        from src.infrastructure.loaders import YamlStoryLoader, YamlStoryLoaderError

        try:
            loader = YamlStoryLoader()
            dto = loader.load_from_file(Path(input_file))
            title = dto.title
            protagonista = dto.protagonista
            relator = dto.relator
            escenarios = dto.escenarios
            sinopsis = dto.sinopsis
            atmosfera = dto.atmosfera
            reglas = dto.reglas
            storyteller_config = dto.storyteller_config
            typed_rules = dto.typed_rules
            personajes_full = dto.personajes_full
        except YamlStoryLoaderError as e:
            raise ValidationError(f"Error al cargar YAML: {e}")

    container = CLIContainer(use_mock=use_mock, provider=provider, debug=debug)
    runner = container.story_runner(output_dir)

    container.reporter.start(title)
    container.reporter.config_summary(profile=settings.active_profile_name)
    t_total = time.perf_counter()

    story = await runner.run_full(
        title=title,
        protagonista=protagonista,
        relator=relator,
        escenarios=escenarios,
        sinopsis=sinopsis,
        atmosfera=atmosfera,
        reglas=reglas or [],
        stop_after=hasta,
        storyteller_config=storyteller_config,
        typed_rules=typed_rules or [],
        personajes_full=personajes_full or [],
    )

    await container.story_repo.update_status(story.id, StoryStatus.COMPLETED.value)

    container.reporter.done(time.perf_counter() - t_total)
    logger.info("[COMANDOS] Historia completada")


def plan(
    title: str,
    use_mock: bool,
    output_dir: Path,
    provider: str | None = None,
) -> None:
    """Generate only the story plan (beats)."""
    logger.info(f"[COMANDOS] Iniciando generación de plan: {title}")

    try:
        import asyncio

        asyncio.run(_plan_async(title, use_mock, output_dir, provider))
    except Exception as e:
        logger.error(f"[COMANDOS] Error al generar el plan: {e}")
        raise GenerationError(str(e)) from e

    logger.info(f"[COMANDOS] Generación de plan completada: {title}")


async def _plan_async(
    title: str,
    use_mock: bool,
    output_dir: Path,  # noqa: ARG001
    provider: str | None = None,
) -> None:
    """Async implementation of plan."""
    await _init_database()

    container = CLIContainer(use_mock=use_mock, provider=provider)
    create_story = container.create_story_use_case()
    create_plan = container.director_use_case()

    story = await create_story.execute(
        title=title,
        protagonista="",
        relator="tercera_persona",
        escenarios="",
        sinopsis="",
        atmosfera="",
    )

    plan_result = await create_plan.execute(story)
    logger.info(f"[COMANDOS] Se han generado {len(plan_result.beats)} beats")


def narrate(
    story_id: str,
    beats: str,
    use_mock: bool,
    provider: str | None = None,
) -> None:
    """Narrate specific beats from an existing story."""
    logger.info(f"[COMANDOS] Iniciando narración para historia: {story_id}")

    try:
        import asyncio

        asyncio.run(_narrate_async(story_id, beats, use_mock, provider))
    except StoryNotFoundError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en la narración: {e}")
        raise GenerationError(str(e)) from e

    logger.info(f"[COMANDOS] Narración completada para historia: {story_id}")


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

    container = CLIContainer(use_mock=use_mock, provider=provider)

    story = await container.story_repo.get_by_id(story_uuid)
    if not story:
        raise StoryNotFoundError(story_id)

    beat_list = [int(b.strip()) for b in beats_csv.split(",") if b.strip().isdigit()]
    if not beat_list:
        raise ValidationError(f"Formato de beats inválido: {beats_csv}")

    all_beats = await container.beat_repo.get_by_story(story_uuid)
    beats_to_narrate = [b for b in all_beats if b.number in beat_list]

    if not beats_to_narrate:
        raise ValidationError("No se encontraron beats que coincidan con la selección")

    narrate_beat = container.voz_use_case()
    for beat in beats_to_narrate:
        logger.info(f"[COMANDOS] Narrando beat #{beat.number}")
        generated_beat, _, _ = await narrate_beat.execute(story, beat)
        await container.beat_repo.save(generated_beat, story_uuid)
        logger.info(f"[COMANDOS] Beat #{beat.number} completado")


def generate_from_db(
    story_id: str,
    use_mock: bool,
    output_dir: Path,
    provider: str | None = None,
    debug: bool = False,
) -> None:
    """Generate story from existing DB entry."""
    logger.info(f"[COMANDOS] Iniciando generación desde BD para historia: {story_id}")

    try:
        import asyncio

        asyncio.run(_generate_from_db_async(story_id, use_mock, output_dir, provider, debug=debug))
    except StoryNotFoundError:
        raise
    except OllamaConnectionError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en la generación desde BD: {e}")
        raise GenerationError(str(e)) from e

    logger.info(f"[COMANDOS] Generación desde BD completada: {story_id}")


async def _generate_from_db_async(
    story_id: str,
    use_mock: bool,
    output_dir: Path,
    provider: str | None = None,
    debug: bool = False,
) -> None:
    """Async implementation of generate_from_db."""
    await _init_database()

    container = CLIContainer(use_mock=use_mock, provider=provider, debug=debug)

    story = await container.story_repo.get_by_string_id(story_id)
    if not story:
        raise StoryNotFoundError(story_id)

    runner = container.story_runner(output_dir)
    container.reporter.start(story.title)
    t_total = time.perf_counter()

    story = await runner.run_from_story(story)

    await container.story_repo.update_status(story.id, StoryStatus.COMPLETED.value)

    container.reporter.done(time.perf_counter() - t_total)
    logger.info("[COMANDOS] Historia completada")


def export_yaml(
    story_id: str,
    output: Path | None = None,
) -> None:
    """Exporta una historia al formato YAML canónico (Spec-217)."""
    logger.info(f"[COMANDOS] Iniciando export-yaml para historia: {story_id}")
    try:
        import asyncio

        asyncio.run(_export_yaml_async(story_id, output))
    except StoryNotFoundError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en export-yaml: {e}")
        raise ExportError(str(e)) from e


async def _export_yaml_async(story_id: str, output: Path | None) -> None:
    """Async impl de export-yaml."""
    await _init_database()

    container = CLIContainer()
    story = await container.story_repo.get_by_string_id(story_id)
    if not story:
        raise StoryNotFoundError(story_id)

    from src.infrastructure.exporters import YamlStoryExporter

    if output is None:
        safe_title = (
            "".join(c for c in story.title if c.isalnum() or c in (" ", "-", "_"))
            .strip()
            .replace(" ", "_")
            .lower()
        )
        output = Path(settings.input_dir) / f"{safe_title}.yaml"

    exporter = YamlStoryExporter()
    written = exporter.export_to_file(story, output)
    logger.info(f"[COMANDOS] YAML exportado a: {written}")
    print(f"YAML escrito en: {written}")


def export_(
    story_id: str,
    format: str,
    output_dir: Path,
    provider: str | None = None,  # noqa: ARG001
) -> None:
    """Export story to file."""
    logger.info(f"[COMANDOS] Iniciando exportación para historia: {story_id}")

    try:
        import asyncio

        asyncio.run(_export_async(story_id, format, output_dir))
    except StoryNotFoundError:
        raise
    except Exception as e:
        logger.error(f"[COMANDOS] Error en la exportación: {e}")
        raise ExportError(str(e))

    logger.info(f"[COMANDOS] Exportación completada para historia: {story_id}")


async def _export_async(
    story_id: str,
    format: str,  # noqa: ARG001
    _output_dir: Path,
) -> None:
    """Async implementation of export."""
    await _init_database()

    try:
        story_uuid = UUID(story_id)
    except ValueError:
        raise ValidationError(f"Formato de UUID inválido: {story_id}")

    container = CLIContainer()

    story = await container.story_repo.get_by_id(story_uuid)
    if not story:
        raise StoryNotFoundError(story_id)

    beats = await container.beat_repo.get_by_story(story_uuid)
    story.beats = beats
    logger.info("[COMANDOS] Historia exportada (sin archivo markdown)")
