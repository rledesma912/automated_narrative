"""CLI Commands for NarrativeForge."""

from pathlib import Path
from uuid import UUID

from src.application.services import PromptBuilder
from src.application.use_cases import (
    CreateStoryPlanUseCase,
    CreateStoryUseCase,
    NarrateBeatUseCase,
)
from src.cli.exceptions import (
    ExportError,
    GenerationError,
    OllamaConnectionError,
    StoryNotFoundError,
    ValidationError,
)
from src.cli.logger import logger
from src.core.orchestrator import StoryRunner
from src.infrastructure.adapters import MockLLMAdapter, OllamaAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.renderers import MarkdownRenderer


def _get_llm_adapter(use_mock: bool):
    """Get LLM adapter based on flag."""
    if use_mock:
        return MockLLMAdapter()
    return OllamaAdapter()


async def _init_database() -> None:
    """Initialize database if needed."""
    try:
        await init_db()
    except Exception as e:
        raise ValidationError(f"Database initialization failed: {e}")


def generate(
    title: str,
    protagonista: str,
    relator: str,
    escenarios: str,
    sinopsis: str,
    atmosfera: str,
    num_beats: int,
    use_mock: bool,
    output_dir: Path,
) -> None:
    """Generate complete story with plan and narrated beats."""
    logger.info(f"Starting story generation: {title}", module="commands", line=1)

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
                num_beats,
                use_mock,
                output_dir,
            )
        )
    except OllamaConnectionError:
        raise
    except Exception as e:
        logger.error(f"Generation failed: {e}", module="commands", line=1)
        raise GenerationError(str(e))

    logger.info(f"Story generation completed: {title}", module="commands", line=1)


async def _generate_async(
    title: str,
    protagonista: str,
    relator: str,
    escenarios: str,
    sinopsis: str,
    atmosfera: str,
    num_beats: int,
    use_mock: bool,
    output_dir: Path,
) -> None:
    """Async implementation of generate."""
    await _init_database()

    llm = _get_llm_adapter(use_mock)
    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()
    prompt_builder = PromptBuilder()

    runner = StoryRunner(
        llm_adapter=llm,
        story_repo=story_repo,
        beat_repo=beat_repo,
        prompt_builder=prompt_builder,
        output_dir=output_dir,
    )

    await runner.run_full(
        title=title,
        protagonista=protagonista,
        relator=relator,
        escenarios=escenarios,
        sinopsis=sinopsis,
        atmosfera=atmosfera,
        num_beats=num_beats,
    )


def plan(
    title: str,
    num_beats: int,
    use_mock: bool,
    output_dir: Path,
) -> None:
    """Generate only the story plan (beats)."""
    logger.info(f"Starting plan generation: {title}", module="commands", line=1)

    try:
        import asyncio

        asyncio.run(_plan_async(title, num_beats, use_mock, output_dir))
    except Exception as e:
        logger.error(f"Plan generation failed: {e}", module="commands", line=1)
        raise GenerationError(str(e))

    logger.info(f"Plan generation completed: {title}", module="commands", line=1)


async def _plan_async(
    title: str,
    num_beats: int,
    use_mock: bool,
    output_dir: Path,  # noqa: ARG001
) -> None:
    """Async implementation of plan."""
    await _init_database()

    llm = _get_llm_adapter(use_mock)
    story_repo = SQLStoryRepository()
    prompt_builder = PromptBuilder()

    create_story = CreateStoryUseCase(story_repo)
    create_plan = CreateStoryPlanUseCase(llm, prompt_builder)

    story = await create_story.execute(
        title=title,
        protagonista="",
        relator="tercera_persona",
        escenarios="",
        sinopsis="",
        atmosfera="",
    )

    plan = await create_plan.execute(story, num_beats=num_beats)
    logger.info(f"Generated {len(plan.beats)} beats", module="commands", line=1)


def narrate(
    story_id: str,
    beats: str,
    use_mock: bool,
) -> None:
    """Narrate specific beats from an existing story."""
    logger.info(f"Starting narration for story: {story_id}", module="commands", line=1)

    try:
        import asyncio

        asyncio.run(_narrate_async(story_id, beats, use_mock))
    except StoryNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Narration failed: {e}", module="commands", line=1)
        raise GenerationError(str(e))

    logger.info(f"Narration completed for story: {story_id}", module="commands", line=1)


async def _narrate_async(
    story_id: str,
    beats_csv: str,
    use_mock: bool,
) -> None:
    """Async implementation of narrate."""
    await _init_database()

    try:
        story_uuid = UUID(story_id)
    except ValueError:
        raise ValidationError(f"Invalid UUID format: {story_id}")

    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()

    story = await story_repo.get_by_id(story_uuid)
    if not story:
        raise StoryNotFoundError(story_id)

    beat_list = [int(b.strip()) for b in beats_csv.split(",") if b.strip().isdigit()]
    if not beat_list:
        raise ValidationError(f"Invalid beats format: {beats_csv}")

    all_beats = await beat_repo.get_by_story(story_uuid)
    beats_to_narrate = [b for b in all_beats if b.number in beat_list]

    if not beats_to_narrate:
        raise ValidationError("No matching beats found")

    llm = _get_llm_adapter(use_mock)
    narrate_beat = NarrateBeatUseCase(llm)

    for beat in beats_to_narrate:
        logger.info(f"Narrating beat #{beat.number}", module="commands", line=1)
        generated_beat, _ = await narrate_beat.execute(story, beat)
        await beat_repo.save(generated_beat, story_uuid)
        logger.info(f"Beat #{beat.number} completed", module="commands", line=1)


def export_(
    story_id: str,
    format: str,
    output_dir: Path,
) -> None:
    """Export story to file."""
    logger.info(f"Starting export for story: {story_id}", module="commands", line=1)

    try:
        import asyncio

        asyncio.run(_export_async(story_id, format, output_dir))
    except StoryNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Export failed: {e}", module="commands", line=1)
        raise ExportError(str(e))

    logger.info(f"Export completed for story: {story_id}", module="commands", line=1)


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
        raise ValidationError(f"Invalid UUID format: {story_id}")

    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()

    story = await story_repo.get_by_id(story_uuid)
    if not story:
        raise StoryNotFoundError(story_id)

    beats = await beat_repo.get_by_story(story_uuid)

    renderer = MarkdownRenderer()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = renderer.render(story, beats, output_dir)

    logger.info(f"Exported to: {output_path}", module="commands", line=1)
