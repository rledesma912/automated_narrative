"""Jobs del asistente de autoría (Spec-530 S3): taller, escaleta y revisión.

Corren en el JobManager como la generación: sobreviven a cerrar la pestaña, un
solo job activo por historia, eventos por el bus y tiempo estimado (Spec-510).
Cada runner relee la historia al arrancar (lo guardado manda) y persiste su
resultado antes de publicar `done`.
"""

from uuid import UUID

from src.application.services.authoring.consultant import WorkshopConsultant
from src.application.services.authoring.planner import OutlinePlanner
from src.application.services.authoring.verifier import OutlineVerifier
from src.application.services.job_manager import JobRunner
from src.application.services.streaming_service import stage_event
from src.domain.jobs import Job, JobKind, JobStage
from src.domain.models import Story
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.database.repositories import SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.presentation.runtime import job_manager


def _done(story_id: UUID, **data) -> StreamEvent:
    return StreamEvent(event=StreamEventType.DONE, data={"story_id": str(story_id), **data})


async def _load(story_id: UUID) -> Story:
    story = await SQLStoryRepository().get_by_id(story_id)
    if story is None:
        raise ValueError(f"Historia no encontrada: {story_id}")
    return story


def consult_runner(story_id: UUID) -> JobRunner:
    def _run():
        async def _gen():
            yield stage_event(JobStage.CONSULTOR, None, None)
            story = await _load(story_id)
            result = await WorkshopConsultant(LLMFactory.get_provider()).analyze(story)
            await SQLStoryRepository().save_workshop_items(story_id, result.items)
            yield _done(story_id, finish={"kind": result.finish.kind, "text": result.finish.text})

        return _gen()

    return _run


def plan_outline_runner(story_id: UUID) -> JobRunner:
    def _run():
        async def _gen():
            llm = LLMFactory.get_provider()
            yield stage_event(JobStage.PLANIFICADOR, None, None)
            story = await _load(story_id)
            acts, _ = await OutlinePlanner(llm).plan(story)
            yield stage_event(JobStage.VERIFICADOR, None, None)
            checked = await OutlineVerifier(llm).verify(story, acts)
            await SQLStoryRepository().save_outline(story_id, checked.outline)
            yield _done(story_id, missing_decisions=checked.missing_decisions)

        return _gen()

    return _run


def verify_outline_runner(story_id: UUID) -> JobRunner:
    def _run():
        async def _gen():
            yield stage_event(JobStage.VERIFICADOR, None, None)
            story = await _load(story_id)
            checked = await OutlineVerifier(LLMFactory.get_provider()).verify(story, story.outline)
            await SQLStoryRepository().save_outline(story_id, checked.outline)
            yield _done(story_id, missing_decisions=checked.missing_decisions)

        return _gen()

    return _run


_RUNNERS = {
    JobKind.CONSULT: consult_runner,
    JobKind.PLAN_OUTLINE: plan_outline_runner,
    JobKind.VERIFY_OUTLINE: verify_outline_runner,
}
AUTHORING_KINDS = tuple(_RUNNERS)


async def submit_authoring(story: Story, kind: JobKind) -> Job:
    """Lanza un job del asistente. Raises JobAlreadyActiveError."""
    return await job_manager.submit(story, kind, _RUNNERS[kind](story.id))
