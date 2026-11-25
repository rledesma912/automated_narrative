"""Job de las miniaturas (Spec-790 §10.7): «Armar las 4».

Corre en el JobManager como el paquete para el video: sobrevive a cerrar la pestaña, un solo
job activo por historia, etapas por el bus y tiempo estimado. Relee la miniatura al arrancar
(lo guardado manda) y la guarda con la tanda nueva antes de publicar `done`.
"""

from uuid import UUID

from src.application.services.job_manager import JobRunner
from src.application.services.miniatura.arnes import Arnes, Etapa, carpeta_de
from src.application.services.streaming_service import stage_event
from src.domain.jobs import Job, JobKind
from src.domain.models import Story
from src.domain.streaming import StreamEvent, StreamEventType
from src.domain.thumbnail import Batch
from src.infrastructure.adapters.comfy.client import ComfyClient, ComfyPort
from src.infrastructure.database.repositories import SQLThumbnailRepository
from src.infrastructure.factories import LLMFactory
from src.messages import message
from src.presentation.runtime import job_manager


def comfy_client() -> ComfyPort:
    """Punto único para reemplazar ComfyUI en los tests."""
    return ComfyClient()


def thumbnail_runner(story_id: UUID) -> JobRunner:
    def _run():
        async def _gen():
            repo = SQLThumbnailRepository()
            thumb = await repo.get(story_id)
            if thumb is None:
                raise ValueError(message("miniatura.no_existe"))
            arnes = Arnes(comfy_client(), carpeta_de(str(story_id)), llm=LLMFactory.get_provider())
            async for paso in arnes.armar(thumb):
                if isinstance(paso, Etapa):
                    yield stage_event(paso.stage, paso.beat, paso.total)
                elif isinstance(paso, Batch):
                    thumb.batches.append(paso)
            await repo.save(thumb)
            yield StreamEvent(event=StreamEventType.DONE, data={"story_id": str(story_id)})

        return _gen()

    return _run


async def submit_thumbnail(story: Story) -> Job:
    """Lanza «Armar las 4». Raises JobAlreadyActiveError."""
    return await job_manager.submit(story, JobKind.THUMBNAIL_BUILD, thumbnail_runner(story.id))
