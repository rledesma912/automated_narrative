"""JobManager — ejecuta jobs de generación en background (Spec-460).

Reemplazó a StreamSessionManager (Spec-220). Cada job corre como una `asyncio.Task` propia,
independiente de cualquier conexión HTTP: cerrar la pestaña no lo detiene, y
cancelarlo (`cancel()`) sí lo detiene de verdad.

Por cada job:
- canal `job:<id>` del EventBus: todos los eventos del pipeline (detalle + prosa);
- canal `global`: ciclo de vida liviano (`job_started`, `job_progress`,
  `job_done`, `job_failed`) para la banda de generación y los botones;
- tabla `generation_job`: estado, etapa y resultado persistidos.

El pipeline se inyecta como `run`: una callable sin args que devuelve un
`AsyncIterator[StreamEvent]` (p.ej. `stream_story(...)`). Así la capa de
aplicación no conoce el cableado del LLM.
"""

import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from uuid import UUID

from src.application.services.event_bus import GLOBAL_CHANNEL, EventBus, job_channel
from src.domain.jobs import (
    CANCELLED_ERROR,
    INTERRUPTED_ERROR,
    NO_RESULT_ERROR,
    Job,
    JobKind,
    JobStage,
    JobStatus,
)
from src.domain.models import Story, StoryStatus
from src.domain.streaming import StreamEvent, StreamEventType
from src.utils.timezone import now_argentina

logger = logging.getLogger(__name__)

CHANNEL_TTL_SECONDS = 600  # el replay del job queda disponible 10 min tras terminar
RECENT_WINDOW = timedelta(seconds=60)  # terminados que entran en el snapshot

JobRunner = Callable[[], AsyncIterator[StreamEvent]]


def _parse_uuid(value) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


class JobAlreadyActiveError(Exception):
    """La historia ya tiene un job `queued`/`running` (→ 409 en la API)."""

    def __init__(self, job_id: UUID | None) -> None:
        super().__init__(f"La historia ya tiene un job activo: {job_id}")
        self.job_id = job_id


class JobManager:
    def __init__(
        self,
        bus: EventBus,
        job_repo,
        story_repo,
        channel_ttl: float = CHANNEL_TTL_SECONDS,
    ) -> None:
        self._bus = bus
        self._jobs = job_repo
        self._stories = story_repo
        self._channel_ttl = channel_ttl
        self._tasks: dict[UUID, asyncio.Task] = {}
        self._cancel_reasons: dict[UUID, str] = {}
        self._titles: dict[UUID, str] = {}
        self._lock = asyncio.Lock()

    # ── API pública ──────────────────────────────────────────────────────────

    async def submit(
        self,
        story: Story,
        kind: JobKind,
        run: JobRunner,
        *,
        params: dict | None = None,
        regenerate: bool = False,
    ) -> Job:
        """Crea el job y lo lanza en background.

        Args:
            regenerate: limpia los artefactos de la generación anterior
                (Spec-216) dentro del job, antes de correr el pipeline.

        Raises:
            JobAlreadyActiveError: la historia ya tiene un job activo.
        """
        async with self._lock:
            active = await self._jobs.get_active_for_story(story.id)
            if active is not None:
                raise JobAlreadyActiveError(active.id)
            job = Job(story_id=story.id, kind=kind, params=params or {})
            try:
                await self._jobs.create(job)
            except sqlite3.IntegrityError:
                # Índice único parcial: otro productor ganó la carrera.
                active = await self._jobs.get_active_for_story(story.id)
                raise JobAlreadyActiveError(active.id if active else None) from None
            self._titles[job.id] = story.title
            self._publish_global(StreamEventType.JOB_STARTED, job)
            self._tasks[job.id] = asyncio.create_task(
                self._run(job, story, run, regenerate), name=f"job:{job.id}"
            )
        return job

    async def cancel(self, job_id: UUID, reason: str = CANCELLED_ERROR) -> bool:
        """Cancela un job en curso y espera a que quede `failed`.

        Returns:
            False si el job no está corriendo en este proceso.
        """
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return False
        self._cancel_reasons[job_id] = reason
        task.cancel()
        await asyncio.wait({task})
        return True

    async def wait(self, job_id: UUID) -> None:
        """Espera a que el job termine (no-op si no está corriendo)."""
        task = self._tasks.get(job_id)
        if task is not None:
            await asyncio.wait({task})

    def is_running(self, job_id: UUID) -> bool:
        task = self._tasks.get(job_id)
        return task is not None and not task.done()

    async def shutdown(self) -> None:
        """Cierre del proceso: los jobs vivos quedan `failed` ("interrumpida")."""
        await asyncio.gather(
            *(self.cancel(job_id, INTERRUPTED_ERROR) for job_id in list(self._tasks))
        )

    async def snapshot(self) -> StreamEvent:
        """Jobs activos + terminados hace menos de `RECENT_WINDOW` (canal global)."""
        active = await self._jobs.list_active()
        recent = await self._jobs.list_recent(since=now_argentina() - RECENT_WINDOW)
        return StreamEvent(
            event=StreamEventType.SNAPSHOT,
            data={
                "active": [await self._payload_for(job) for job in active],
                "recent": [await self._payload_for(job) for job in recent],
            },
        )

    # ── Ejecución ────────────────────────────────────────────────────────────

    async def _run(self, job: Job, story: Story, run: JobRunner, regenerate: bool) -> None:
        channel = job_channel(job.id)
        status, error, narrative_id = JobStatus.FAILED, NO_RESULT_ERROR, None
        try:
            await self._jobs.mark_running(job.id)
            job.status = JobStatus.RUNNING
            if regenerate:
                await self._stories.clear_story_artifacts(story.id)

            finished = False
            async for event in run():
                self._bus.publish(channel, event)
                data = event.data if isinstance(event.data, dict) else {}
                if event.event == StreamEventType.STATUS and data.get("stage"):
                    await self._record_progress(job, data)
                elif event.event == StreamEventType.DONE:
                    status, error, narrative_id = JobStatus.DONE, None, data.get("narrative_id")
                    finished = True
                elif event.event == StreamEventType.ERROR:
                    status, error = JobStatus.FAILED, data.get("msg") or "error en el pipeline"
                    finished = True
            if not finished:
                self._publish_error(channel, NO_RESULT_ERROR)
        except asyncio.CancelledError:
            error = self._cancel_reasons.pop(job.id, CANCELLED_ERROR)
            status = JobStatus.FAILED
            self._publish_error(channel, error, cancelled=True)
            # Solo una generación completa deja la historia a medias; cancelar la
            # regeneración de un acto no invalida la historia ya generada.
            if job.kind == JobKind.FULL_GENERATION:
                await self._stories.update_status(story.id, StoryStatus.FAILED.value)
        except Exception as exc:  # noqa: BLE001 — cualquier fallo deja el job en failed
            logger.exception("[JOB] Falló el job %s", job.id)
            status, error = JobStatus.FAILED, str(exc)
            self._publish_error(channel, error)
        finally:
            await self._finish(job, status, error, narrative_id)

    async def _record_progress(self, job: Job, data: dict) -> None:
        stage = JobStage(data["stage"])
        beat = data.get("beat")
        total = data.get("total_beats")
        if (stage, beat) == (job.stage, job.beat):
            return
        job.stage, job.beat = stage, beat
        if total is not None:
            job.total_beats = total
        await self._jobs.update_progress(job.id, stage, beat, total_beats=total)
        self._publish_global(StreamEventType.JOB_PROGRESS, job)

    async def _finish(
        self, job: Job, status: JobStatus, error: str | None, narrative_id: str | None
    ) -> None:
        """Cierre del job. No debe fallar: siempre publica el evento final y agenda el TTL."""
        parsed_narrative_id = _parse_uuid(narrative_id)
        if narrative_id and parsed_narrative_id is None:
            logger.warning("[JOB] narrative_id inválido en job %s: %r", job.id, narrative_id)
        try:
            await self._jobs.finish(job.id, status, error=error, narrative_id=parsed_narrative_id)
        except Exception:  # noqa: BLE001 — el evento global sale igual
            logger.exception("[JOB] No se pudo persistir el final del job %s", job.id)
        job.status, job.error, job.narrative_id = status, error, parsed_narrative_id
        self._publish_global(
            StreamEventType.JOB_DONE if status == JobStatus.DONE else StreamEventType.JOB_FAILED,
            job,
        )
        self._tasks.pop(job.id, None)
        asyncio.get_running_loop().call_later(
            self._channel_ttl, self._bus.drop, job_channel(job.id)
        )

    # ── Eventos ──────────────────────────────────────────────────────────────

    def _publish_error(self, channel: str, msg: str, cancelled: bool = False) -> None:
        data: dict = {"msg": msg}
        if cancelled:
            data["cancelled"] = True
        self._bus.publish(channel, StreamEvent(event=StreamEventType.ERROR, data=data))

    def _publish_global(self, event_type: StreamEventType, job: Job) -> None:
        payload = self._payload(job, self._titles.get(job.id, ""))
        self._bus.publish(GLOBAL_CHANNEL, StreamEvent(event=event_type, data=payload))

    async def _payload_for(self, job: Job) -> dict:
        title = self._titles.get(job.id)
        if title is None:
            story = await self._stories.get_by_id(job.story_id)
            title = story.title if story else ""
        return self._payload(job, title)

    @staticmethod
    def _payload(job: Job, title: str) -> dict:
        return {
            "job_id": str(job.id),
            "story_id": str(job.story_id),
            "title": title,
            "kind": job.kind.value,
            "status": job.status.value,
            "stage": job.stage.value if job.stage else None,
            "beat": job.beat,
            "total_beats": job.total_beats,
            "narrative_id": str(job.narrative_id) if job.narrative_id else None,
            "error": job.error,
            "params": job.params,
        }
