"""CLI Commands for NarrativeForge."""

import time
from pathlib import Path

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
    genero: str,
    use_mock: bool,
    output_dir: Path,
    input_file: str | None = None,
    provider: str | None = None,
    debug: bool = False,
) -> None:
    """Genera la historia completa: escaleta (si falta) y los actos narrados."""
    reglas: list[str] = []
    narrator_config: dict | None = None
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
                genero,
                use_mock,
                output_dir,
                provider,
                reglas,
                debug=debug,
                narrator_config=narrator_config,
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
    genero: str,
    use_mock: bool,
    output_dir: Path,
    provider: str | None = None,
    reglas: list[str] | None = None,
    debug: bool = False,
    narrator_config: dict | None = None,
    typed_rules: list[dict] | None = None,
    personajes_full: list[dict] | None = None,
    input_file: str | None = None,
    subgenero: str = "",
    tono: str = "",
    escenarios_full: list[dict] | None = None,
) -> None:
    """Async implementation of generate."""
    await _init_database()
    # Solo vienen del YAML (--input): entidades (Spec-450) y el texto de cada acto.
    entities: list[dict] = []
    actos: list[dict] = []

    if input_file:
        from src.infrastructure.loaders import YamlStoryLoader, YamlStoryLoaderError

        try:
            loader = YamlStoryLoader()
            dto = loader.load_from_file(Path(input_file))
            title = dto.title
            protagonista = dto.protagonista
            relator = dto.relator
            escenarios = dto.escenarios
            escenarios_full = dto.escenarios_full
            sinopsis = dto.sinopsis
            genero = dto.genero
            subgenero = dto.subgenero
            tono = dto.tono
            reglas = dto.reglas
            narrator_config = dto.narrator_config
            typed_rules = dto.typed_rules
            personajes_full = dto.personajes_full
            entities = dto.entities
            actos = dto.actos
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
        genero=genero,
        subgenero=subgenero,
        tono=tono,
        reglas=reglas or [],
        narrator_config=narrator_config,
        typed_rules=typed_rules or [],
        personajes_full=personajes_full or [],
        escenarios_full=escenarios_full or [],
        entities=entities,
        actos=actos,
    )

    await container.story_repo.update_status(story.id, StoryStatus.COMPLETED.value)

    container.reporter.done(time.perf_counter() - t_total)
    logger.info("[COMANDOS] Historia completada")


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


def _safe_title(title: str) -> str:
    return (
        "".join(c for c in title if c.isalnum() or c in (" ", "-", "_"))
        .strip()
        .replace(" ", "_")
        .lower()
    )


async def _export_yaml_async(story_id: str, output: Path | None) -> None:
    """Async impl de export-yaml."""
    await _init_database()

    container = CLIContainer()
    story = await container.story_repo.get_by_string_id(story_id)
    if not story:
        raise StoryNotFoundError(story_id)

    from src.infrastructure.exporters import YamlStoryExporter

    if output is None:
        output = Path(settings.input_dir) / f"{_safe_title(story.title)}.yaml"

    exporter = YamlStoryExporter()
    written = exporter.export_to_file(story, output)
    logger.info(f"[COMANDOS] YAML exportado a: {written}")
    print(f"YAML escrito en: {written}")


def export_all_yaml(output_dir: Path) -> None:
    """Exporta todas las historias a `output_dir`, una por archivo (Spec-440 T2.4)."""
    logger.info(f"[COMANDOS] Iniciando export-yaml --all en: {output_dir}")
    try:
        import asyncio

        asyncio.run(_export_all_yaml_async(output_dir))
    except Exception as e:
        logger.error(f"[COMANDOS] Error en export-yaml --all: {e}")
        raise ExportError(str(e)) from e


async def _export_all_yaml_async(output_dir: Path) -> None:
    from src.infrastructure.exporters import YamlStoryExporter

    await _init_database()
    container = CLIContainer()
    exporter = YamlStoryExporter()
    output_dir.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    for summary in await container.story_repo.list_all():
        story = await container.story_repo.get_by_id(summary.id)
        if story is None:
            continue
        name = _safe_title(story.title) or "historia"
        if name in used:  # títulos repetidos: se desambigua con el id
            name = f"{name}_{str(story.id)[:8]}"
        used.add(name)
        written = exporter.export_to_file(story, output_dir / f"{name}.yaml")
        print(f"YAML escrito en: {written}")


def import_yaml(files: list[Path], drop_invalid_subgenre: bool = False) -> None:
    """Crea cada historia del YAML como borrador, sin llamar al LLM (Spec-440 T2.4).

    Con `drop_invalid_subgenre`, un subgénero que no corresponde a su género se
    descarta (queda el género) con un aviso, en vez de rechazar el archivo.
    """
    import asyncio

    failed = asyncio.run(_import_yaml_async(files, drop_invalid_subgenre))
    if failed:
        raise ValidationError(f"{failed} de {len(files)} archivo(s) no se importaron")


async def _import_yaml_async(files: list[Path], drop_invalid_subgenre: bool) -> int:
    from src.application.use_cases.create_story import CreateStoryUseCase
    from src.domain.exceptions import InvalidStoryInputError
    from src.infrastructure.database.repositories import SQLGenreRepository
    from src.infrastructure.loaders import YamlStoryLoader, YamlStoryLoaderError

    await _init_database()
    genres = SQLGenreRepository()
    use_case = CreateStoryUseCase(CLIContainer().story_repo, genres)
    loader = YamlStoryLoader()
    failed = 0
    for path in files:
        try:
            # Relativo al cwd si existe; si no, el loader lo busca en input_dir.
            dto = loader.load_from_file(path.resolve() if path.exists() else path)
            if (
                drop_invalid_subgenre
                and dto.subgenero
                and await genres.exists(dto.genero)
                and not await genres.exists(dto.genero, dto.subgenero)
            ):
                print(
                    f"Aviso: {path}: se descarta el subgénero '{dto.subgenero}' "
                    f"(no corresponde a '{dto.genero}'); elegí uno válido en el wizard."
                )
                dto.subgenero = ""
            story = await use_case.execute(dto, initial_status=StoryStatus.DRAFT)
            print(f"Importada: {story.title} ({story.id})")
        except (YamlStoryLoaderError, InvalidStoryInputError) as e:
            failed += 1
            message = e.message if isinstance(e, InvalidStoryInputError) else str(e)
            logger.error(f"[COMANDOS] import-yaml {path}: {message}")
            print(f"Error: {path}: {message}")
    return failed
