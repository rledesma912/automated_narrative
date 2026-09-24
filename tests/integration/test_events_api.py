"""Canal global de eventos `GET /api/v1/events` (Spec-460 T5.1).

El stream es infinito: se prueba el generador directamente (el transporte ASGI
de httpx espera a que la respuesta termine).
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from src.application.services.event_bus import GLOBAL_CHANNEL
from src.config import settings
from src.domain.jobs import JobKind
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.database.connection import get_connection, init_db
from src.presentation.routers.events_router import stream_global_events
from src.presentation.runtime import event_bus, job_manager


@pytest.fixture(autouse=True)
async def db(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
    await init_db()


async def _story(title: str = "La pena del colectivo"):
    story_id = uuid.uuid4()
    conn = await get_connection()
    await conn.execute("INSERT INTO story (id, title) VALUES (?, ?)", (str(story_id), title))
    await conn.commit()
    await conn.close()
    return SimpleNamespace(id=story_id, title=title)


def _run(block: asyncio.Event | None = None):
    async def _gen() -> AsyncIterator[StreamEvent]:
        yield StreamEvent(
            event=StreamEventType.STATUS,
            data={"msg": "x", "stage": "voz", "beat": 1, "total_beats": 5},
        )
        if block:
            await block.wait()
        yield StreamEvent(event=StreamEventType.DONE, data={"narrative_id": None})

    return _gen


async def _next(stream) -> dict:
    sse = await asyncio.wait_for(anext(stream), timeout=2)
    return {**sse, "data": json.loads(sse["data"])}


async def test_primer_evento_es_el_snapshot_con_los_jobs_activos():
    story = await _story()
    block = asyncio.Event()
    job = await job_manager.submit(story, JobKind.FULL_GENERATION, _run(block))
    await asyncio.sleep(0.05)
    stream = stream_global_events()

    first = await _next(stream)

    assert first["event"] == "snapshot"
    assert "id" not in first  # el snapshot no consume ids del canal
    active = first["data"]["active"]
    assert [(j["job_id"], j["title"], j["stage"]) for j in active] == [
        (str(job.id), "La pena del colectivo", "voz")
    ]
    block.set()
    await job_manager.wait(job.id)
    await stream.aclose()


async def test_eventos_de_jobs_llegan_en_vivo():
    stream = stream_global_events()
    await _next(stream)  # snapshot
    story = await _story()

    job = await job_manager.submit(story, JobKind.FULL_GENERATION, _run())
    kinds = [(await _next(stream))["event"] for _ in range(3)]

    assert kinds == ["job_started", "job_progress", "job_done"]
    await job_manager.wait(job.id)
    await stream.aclose()


async def test_heartbeat_si_no_hay_actividad():
    stream = stream_global_events(heartbeat_interval=0.05)
    await _next(stream)  # snapshot

    hb = await _next(stream)

    assert hb["event"] == "heartbeat"
    assert "id" not in hb
    await stream.aclose()


async def test_sin_last_event_id_no_reenvia_eventos_viejos():
    story = await _story()
    job = await job_manager.submit(story, JobKind.FULL_GENERATION, _run())
    await job_manager.wait(job.id)  # eventos ya publicados antes de conectar

    stream = stream_global_events(heartbeat_interval=0.05)
    await _next(stream)  # snapshot

    assert (await _next(stream))["event"] == "heartbeat"
    await stream.aclose()


async def test_reconexion_con_last_event_id_reenvia_lo_perdido():
    story = await _story()
    stream = stream_global_events()
    await _next(stream)  # snapshot
    block = asyncio.Event()
    job = await job_manager.submit(story, JobKind.FULL_GENERATION, _run(block))
    started = await _next(stream)
    await stream.aclose()  # corte de red después de job_started

    block.set()
    await job_manager.wait(job.id)  # job_progress y job_done ocurren sin nosotros
    resumed = stream_global_events(last_event_id=int(started["id"]))

    kinds = [(await _next(resumed))["event"] for _ in range(3)]

    assert kinds == ["snapshot", "job_progress", "job_done"]
    await resumed.aclose()


async def test_cerrar_la_conexion_desuscribe():
    stream = stream_global_events()
    await _next(stream)
    subscribers = len(event_bus._channel(GLOBAL_CHANNEL).subscribers)

    await stream.aclose()

    assert len(event_bus._channel(GLOBAL_CHANNEL).subscribers) == subscribers - 1
