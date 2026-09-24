"""Arranque de generaciones como jobs (Spec-460).

Cablea los pipelines reales (LLM + casos de uso + repos) y los entrega al
JobManager: la generación completa y la regeneración de la Voz de un acto.
"""

from uuid import UUID

from src.application.services import PromptBuilder
from src.application.services.job_manager import JobRunner
from src.application.services.observability_service import observability
from src.application.services.streaming_service import stage_event, stream_story
from src.application.use_cases.director_use_case import DirectorUseCase
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.application.use_cases.regenerate_beat_voz_use_case import RegenerateBeatVozUseCase
from src.domain.jobs import Job, JobKind, JobStage
from src.domain.models import Story
from src.domain.streaming import StreamEvent, StreamEventType
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


def regenerate_voz_runner(story: Story, beat: int, narrative_id: UUID) -> JobRunner:
    """Re-narración de la Voz de un acto (Spec-430, 1 llamada LLM) como runner."""

    def _run():
        async def _gen():
            prompt_builder = PromptBuilder()
            yield stage_event(JobStage.VOZ, beat, prompt_builder.num_beats)
            use_case = RegenerateBeatVozUseCase(
                llm=LLMFactory.get_provider(),
                prompt_builder=prompt_builder,
                story_repo=SQLStoryRepository(),
                beat_repo=SQLBeatRepository(),
                narrative_use_case=GenerateNarrativesUseCase(),
            )
            _beat, narrative = await use_case.execute(story.id, beat, narrative_id)
            yield StreamEvent(
                event=StreamEventType.DONE,
                data={"story_id": str(story.id), "narrative_id": str(narrative.id), "beat": beat},
            )

        return _gen()

    return _run


async def submit_regenerate_voz(story: Story, beat: int, narrative_id: UUID) -> Job:
    """Lanza la regeneración de la Voz del acto `beat` del relato `narrative_id`.

    Raises:
        JobAlreadyActiveError: la historia ya tiene un job activo.
    """
    return await job_manager.submit(
        story,
        JobKind.REGENERATE_VOZ,
        regenerate_voz_runner(story, beat, narrative_id),
        params={"beat": beat, "narrative_id": str(narrative_id)},
    )
