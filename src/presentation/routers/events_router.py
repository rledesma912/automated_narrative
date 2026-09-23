"""Canal global de eventos (Spec-460 S5).

`GET /api/v1/events` — una conexión por pestaña. Emite:
- `snapshot` al conectar: jobs activos y terminados hace menos de 60 s;
- `job_started` / `job_progress` / `job_done` / `job_failed` en vivo;
- `heartbeat` cada 15 s sin actividad (también indica que el Core responde).

Liviano: nunca lleva prosa. Al reconectar con `Last-Event-ID` se reenvían los
eventos perdidos después del snapshot.
"""

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header
from sse_starlette.sse import EventSourceResponse

from src.application.services.event_bus import GLOBAL_CHANNEL
from src.domain.streaming import StreamEvent, StreamEventType
from src.presentation.routers.job_router import parse_last_event_id
from src.presentation.runtime import event_bus, job_manager

router = APIRouter(tags=["Events"])

HEARTBEAT_INTERVAL = 15  # segundos — Spec-201


@router.get("/events")
async def global_events(last_event_id: str | None = Header(None)):
    return EventSourceResponse(stream_global_events(parse_last_event_id(last_event_id)))


async def stream_global_events(
    last_event_id: int | None = None, heartbeat_interval: float = HEARTBEAT_INTERVAL
) -> AsyncIterator[dict]:
    # Suscribirse antes del snapshot: lo que pase en el medio llega por la queue.
    queue, replay = event_bus.subscribe(GLOBAL_CHANNEL, last_event_id)
    try:
        yield (await job_manager.snapshot()).to_sse()
        if last_event_id is not None:  # reconexión: lo que se perdió
            for event in replay:
                yield event.to_sse()
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except asyncio.TimeoutError:
                event = StreamEvent(event=StreamEventType.HEARTBEAT, data={"alive": True})
            yield event.to_sse()
    finally:
        event_bus.unsubscribe(GLOBAL_CHANNEL, queue)
