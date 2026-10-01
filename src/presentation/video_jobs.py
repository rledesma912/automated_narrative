"""Job del paquete para el video (Spec-610 T2.5).

Corre en el JobManager como los del asistente: sobrevive a cerrar la pestaña, un solo
job activo por historia, eventos por el bus y tiempo estimado. Relee la historia y el
relato al arrancar (lo guardado manda) y guarda el paquete antes de publicar `done`.
"""

from uuid import UUID

from src.application.services.job_manager import JobRunner
from src.application.services.streaming_service import stage_event
from src.application.services.video.service import VideoScriptService
from src.domain.jobs import Job, JobKind, JobStage
from src.domain.models import Story
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.database.repositories import (
    SQLGeneratedNarrativeRepository,
    SQLStoryRepository,
    SQLVideoScriptRepository,
)
from src.infrastructure.factories import LLMFactory
from src.presentation.runtime import job_manager


def video_script_runner(story_id: UUID, narrative_id: UUID) -> JobRunner:
    def _run():
        async def _gen():
            yield stage_event(JobStage.GUIONISTA, None, None)
            story = await SQLStoryRepository().get_by_id(story_id)
            narrative = await SQLGeneratedNarrativeRepository().get_by_id(narrative_id)
            if story is None or narrative is None:
                raise ValueError(f"Historia o relato no encontrado: {story_id} / {narrative_id}")
            script = await VideoScriptService(LLMFactory.get_provider()).generate(story, narrative)
            await SQLVideoScriptRepository().save(script)
            yield StreamEvent(
                event=StreamEventType.DONE,
                data={"story_id": str(story_id), "narrative_id": str(narrative_id)},
            )

        return _gen()

    return _run


async def submit_video_script(story: Story, narrative_id: UUID) -> Job:
    """Lanza el armado del paquete. Raises JobAlreadyActiveError."""
    return await job_manager.submit(
        story,
        JobKind.VIDEO_SCRIPT,
        video_script_runner(story.id, narrative_id),
        params={"narrative_id": str(narrative_id)},
    )
