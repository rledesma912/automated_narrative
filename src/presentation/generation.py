"""Arranque de generaciones como jobs (Spec-460).

Cablea el pipeline real (LLM + Director + repos) y lo entrega al JobManager.
Lo usan el router de jobs y el endpoint SSE legado `/stories/{id}/stream`.
"""

from src.application.services import PromptBuilder
from src.application.services.job_manager import JobRunner
from src.application.services.observability_service import observability
from src.application.services.streaming_service import stream_story
from src.application.use_cases.director_use_case import DirectorUseCase
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.domain.jobs import Job, JobKind
from src.domain.models import Story
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.infrastructure.normalizers import ResponseNormalizer
from src.presentation.runtime import job_manager


def full_generation_runner(story: Story) -> JobRunner:
    """Pipeline completo (17 llamadas LLM) como runner del JobManager."""

    def _run():
        story_repo = SQLStoryRepository()
        director = DirectorUseCase(
            llm=LLMFactory.get_provider(),
            prompt_builder=PromptBuilder(),
            normalizer=ResponseNormalizer(),
            story_repo=story_repo,
        )
        return stream_story(
            director,
            story,
            story_repo=story_repo,
            beat_repo=SQLBeatRepository(),
            narrative_use_case=GenerateNarrativesUseCase(),
        )

    return _run


async def submit_full_generation(story: Story) -> Job:
    """Lanza la generación completa de `story`.

    Siempre parte de cero: limpia beats/journal/anchors previos dentro del job
    (Spec-216), igual que el `PATCH status=processing` que hacía el frontend.

    Raises:
        JobAlreadyActiveError: la historia ya tiene un job activo.
    """
    job = await job_manager.submit(
        story, JobKind.FULL_GENERATION, full_generation_runner(story), regenerate=True
    )
    observability.record(
        category="generation",
        message=f"Iniciando generación de '{story.title}'",
        story_id=str(story.id),
        story_title=story.title,
    )
    return job
