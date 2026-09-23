"""Job router — comandos de generación y SSE de detalle por job (Spec-460 S3)."""

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from src.application.services.event_bus import job_channel
from src.application.services.job_manager import JobAlreadyActiveError
from src.domain.jobs import Job, JobKind, JobStatus
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.database.repositories import (
    SQLBeatRepository,
    SQLJobRepository,
    SQLStoryRepository,
)
from src.presentation.generation import submit_full_generation
from src.presentation.runtime import event_bus, job_manager
from src.presentation.schemas.request import JobCreateRequest
from src.presentation.schemas.response import JobResponse

router = APIRouter(tags=["Jobs"])

_TERMINAL_EVENTS = (StreamEventType.DONE, StreamEventType.ERROR)


def _to_response(job: Job) -> JobResponse:
    return JobResponse(
        job_id=str(job.id),
        story_id=str(job.story_id),
        kind=job.kind.value,
        status=job.status.value,
        stage=job.stage.value if job.stage else None,
        beat=job.beat,
        total_beats=job.total_beats,
        error=job.error,
        narrative_id=str(job.narrative_id) if job.narrative_id else None,
    )


def _already_active(job_id: UUID | None) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": "La historia ya tiene una generación en curso",
            "job_id": str(job_id) if job_id else None,
        },
    )


async def _get_job_or_404(job_id: str) -> Job:
    try:
        job = await SQLJobRepository().get(UUID(job_id))
    except ValueError:
        job = None
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job no encontrado: {job_id}")
    return job


@router.post("/stories/{story_id}/jobs", status_code=202, response_model=JobResponse)
async def create_job(story_id: str, request: JobCreateRequest):
    """Lanza un job sobre la historia y responde al instante (202)."""
    story = await SQLStoryRepository().get_by_id(UUID(story_id))
    if story is None:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")
    if request.kind != JobKind.FULL_GENERATION:
        raise HTTPException(status_code=422, detail=f"Tipo de job no soportado: {request.kind}")
    try:
        job = await submit_full_generation(story)
    except JobAlreadyActiveError as exc:
        return _already_active(exc.job_id)
    return _to_response(job)


@router.get("/stories/{story_id}/jobs/active", response_model=JobResponse)
async def get_active_job(story_id: str):
    """Job en curso de la historia (404 si no hay)."""
    try:
        job = await SQLJobRepository().get_active_for_story(UUID(story_id))
    except ValueError:
        job = None
    if job is None:
        raise HTTPException(status_code=404, detail="La historia no tiene un job en curso")
    return _to_response(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    return _to_response(await _get_job_or_404(job_id))


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str):
    """Cancela un job en curso: detiene el pipeline y lo deja `failed`."""
    job = await _get_job_or_404(job_id)
    if not await job_manager.cancel(job.id):
        raise HTTPException(status_code=409, detail="El job no está en curso")
    return _to_response(await _get_job_or_404(job_id))


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, last_event_id: str | None = Header(None)):
    """SSE de detalle del job: replay + eventos en vivo. Nunca arranca trabajo."""
    job = await _get_job_or_404(job_id)
    return EventSourceResponse(stream_job_events(job, parse_last_event_id(last_event_id)))


def parse_last_event_id(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


async def stream_job_events(job: Job, last_event_id: int | None = None) -> AsyncIterator[dict]:
    """Eventos SSE de un job, listos para `EventSourceResponse`.

    - Job activo o terminado hace poco (canal vivo): replay desde `last_event_id`
      y después en vivo, hasta `done`/`stream_error`.
    - Canal ya descartado (TTL): reproduce los beats desde la DB y cierra.
    """
    channel = job_channel(job.id)
    if not (job.is_active or event_bus.has_channel(channel)):
        async for event in _replay_from_db(job):
            yield event.to_sse()
        return

    queue, replay = event_bus.subscribe(channel, last_event_id)
    try:
        for event in replay:
            yield event.to_sse()
            if event.event in _TERMINAL_EVENTS:
                return
        while True:
            event = await queue.get()
            yield event.to_sse()
            if event.event in _TERMINAL_EVENTS:
                return
    finally:
        event_bus.unsubscribe(channel, queue)


async def _replay_from_db(job: Job) -> AsyncIterator[StreamEvent]:
    for beat in await SQLBeatRepository().get_by_story(job.story_id):
        if beat.generated_act:
            yield StreamEvent(
                event=StreamEventType.BEAT_DONE,
                data={"number": beat.number, "content": beat.generated_act},
            )
    if job.status == JobStatus.DONE:
        yield StreamEvent(
            event=StreamEventType.DONE,
            data={
                "story_id": str(job.story_id),
                "narrative_id": str(job.narrative_id) if job.narrative_id else None,
                "read_only": True,
            },
        )
    else:
        yield StreamEvent(event=StreamEventType.ERROR, data={"msg": job.error or "falló"})
