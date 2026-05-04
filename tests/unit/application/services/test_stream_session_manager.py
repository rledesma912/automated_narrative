"""Tests unitarios para StreamSessionManager (Spec-220 Slice B).

asyncio_mode = "auto" en pyproject.toml → no se necesita @pytest.mark.asyncio.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest

from src.application.services.stream_session_manager import (
    REPLAY_BUFFER_MAXLEN,
    StreamSessionManager,
)
from src.domain.streaming import StreamEvent, StreamEventType


def _evt(kind: StreamEventType, data: dict | None = None) -> StreamEvent:
    return StreamEvent(event=kind, data=data or {})


async def _gen_events(events: list[StreamEvent], delay: float = 0.0) -> AsyncIterator[StreamEvent]:
    for e in events:
        if delay:
            await asyncio.sleep(delay)
        yield e


@pytest.fixture
def manager() -> StreamSessionManager:
    """Manager fresco por test (instancia propia, no el singleton del módulo)."""
    return StreamSessionManager()


# ── 1 ─────────────────────────────────────────────────────────────────────────
async def test_attach_creates_session_first_time(manager: StreamSessionManager):
    factory_calls: list[int] = []

    def factory() -> AsyncIterator[StreamEvent]:
        factory_calls.append(1)
        return _gen_events([_evt(StreamEventType.DONE, {"ok": True})])

    queue, replay = await manager.attach("s1", factory)
    await asyncio.sleep(0.05)  # dar tiempo al productor a correr

    assert len(factory_calls) == 1
    assert manager.is_active("s1")
    assert isinstance(queue, asyncio.Queue)
    assert replay == []  # primer cliente, sin eventos previos


# ── 2 ─────────────────────────────────────────────────────────────────────────
async def test_attach_reuses_existing_session(manager: StreamSessionManager):
    factory_calls: list[int] = []

    def factory() -> AsyncIterator[StreamEvent]:
        factory_calls.append(1)

        async def _hold() -> AsyncIterator[StreamEvent]:
            await asyncio.sleep(0.5)  # productor "lento" que no termina
            yield _evt(StreamEventType.DONE)

        return _hold()

    await manager.attach("s1", factory)
    await manager.attach("s1", factory)  # segundo attach
    await manager.attach("s1", factory)  # tercer attach
    await asyncio.sleep(0.05)  # ceder al event loop para que el productor task se inicie

    assert len(factory_calls) == 1, "factory debe invocarse solo la primera vez"
    assert manager.is_active("s1")


# ── 3 ─────────────────────────────────────────────────────────────────────────
async def test_attach_returns_replay_buffer_snapshot(manager: StreamSessionManager):
    pre_events = [
        _evt(StreamEventType.STATUS, {"msg": "fase 1"}),
        _evt(StreamEventType.BEAT_START, {"number": 1}),
        _evt(StreamEventType.BEAT_DONE, {"number": 1, "content": "..."}),
    ]

    block = asyncio.Event()

    def factory() -> AsyncIterator[StreamEvent]:
        async def _gen() -> AsyncIterator[StreamEvent]:
            for e in pre_events:
                yield e
            await block.wait()  # mantiene productor vivo
            yield _evt(StreamEventType.DONE)

        return _gen()

    # Cliente A llega primero
    await manager.attach("s1", factory)
    await asyncio.sleep(0.05)  # esperar a que productor emita pre_events

    # Cliente B llega tarde
    queue_b, replay_b = await manager.attach("s1", factory)

    assert len(replay_b) == 3
    assert [e.event for e in replay_b] == [
        StreamEventType.STATUS,
        StreamEventType.BEAT_START,
        StreamEventType.BEAT_DONE,
    ]

    # Cleanup
    block.set()
    await asyncio.sleep(0.05)


# ── 4 ─────────────────────────────────────────────────────────────────────────
async def test_detach_removes_consumer(manager: StreamSessionManager):
    block = asyncio.Event()

    def factory() -> AsyncIterator[StreamEvent]:
        async def _gen() -> AsyncIterator[StreamEvent]:
            yield _evt(StreamEventType.STATUS, {"msg": "go"})
            await block.wait()
            yield _evt(StreamEventType.DONE)

        return _gen()

    queue, _ = await manager.attach("s1", factory)
    await asyncio.sleep(0.05)

    session = manager._sessions["s1"]
    assert queue in session.consumers

    await manager.detach("s1", queue)
    assert queue not in session.consumers

    block.set()
    await asyncio.sleep(0.05)


# ── 5 ─────────────────────────────────────────────────────────────────────────
async def test_detach_cleans_session_when_last_consumer_leaves_after_done(
    manager: StreamSessionManager,
):
    def factory() -> AsyncIterator[StreamEvent]:
        return _gen_events([_evt(StreamEventType.DONE, {"ok": True})])

    queue, _ = await manager.attach("s1", factory)
    # Esperar a que el productor emita DONE y setee done_event
    await asyncio.sleep(0.05)
    assert manager._sessions["s1"].done_event.is_set()

    # Detach del único consumer → la sesión debe eliminarse del registry
    await manager.detach("s1", queue)
    assert not manager.is_active("s1")


# ── 6 ─────────────────────────────────────────────────────────────────────────
async def test_broadcast_skips_heartbeat_in_replay_buffer(manager: StreamSessionManager):
    block = asyncio.Event()

    def factory() -> AsyncIterator[StreamEvent]:
        async def _gen() -> AsyncIterator[StreamEvent]:
            yield _evt(StreamEventType.HEARTBEAT, {"alive": True})
            yield _evt(StreamEventType.STATUS, {"msg": "x"})
            yield _evt(StreamEventType.HEARTBEAT, {"alive": True})
            yield _evt(StreamEventType.BEAT_DONE, {"number": 1})
            await block.wait()
            yield _evt(StreamEventType.DONE)

        return _gen()

    queue_a, _ = await manager.attach("s1", factory)
    await asyncio.sleep(0.05)

    # El consumidor en vivo SÍ debe haber recibido los heartbeats
    received_kinds: list[StreamEventType] = []
    while not queue_a.empty():
        received_kinds.append(queue_a.get_nowait().event)
    assert StreamEventType.HEARTBEAT in received_kinds

    # Pero el replay buffer NO debe contener heartbeats
    _, replay_b = await manager.attach("s1", factory)
    assert all(e.event != StreamEventType.HEARTBEAT for e in replay_b)
    assert [e.event for e in replay_b] == [
        StreamEventType.STATUS,
        StreamEventType.BEAT_DONE,
    ]

    block.set()
    await asyncio.sleep(0.05)


# ── 7 ─────────────────────────────────────────────────────────────────────────
async def test_concurrent_attach_creates_only_one_session(manager: StreamSessionManager):
    factory_calls: list[int] = []
    block = asyncio.Event()

    def factory() -> AsyncIterator[StreamEvent]:
        factory_calls.append(1)

        async def _gen() -> AsyncIterator[StreamEvent]:
            await block.wait()
            yield _evt(StreamEventType.DONE)

        return _gen()

    # 10 attaches concurrentes al mismo story_id
    results = await asyncio.gather(*[manager.attach("s1", factory) for _ in range(10)])

    assert len(factory_calls) == 1, (
        f"factory debe invocarse 1 sola vez bajo concurrencia (fue {len(factory_calls)})"
    )
    session = manager._sessions["s1"]
    assert len(session.consumers) == 10

    # Cleanup
    block.set()
    await asyncio.sleep(0.05)


# ── Bonus: replay buffer respeta maxlen ──────────────────────────────────────
async def test_replay_buffer_respects_maxlen(manager: StreamSessionManager):
    block = asyncio.Event()

    def factory() -> AsyncIterator[StreamEvent]:
        async def _gen() -> AsyncIterator[StreamEvent]:
            for i in range(REPLAY_BUFFER_MAXLEN + 20):
                yield _evt(StreamEventType.STATUS, {"i": i})
            await block.wait()
            yield _evt(StreamEventType.DONE)

        return _gen()

    await manager.attach("s1", factory)
    await asyncio.sleep(0.1)

    _, replay = await manager.attach("s1", factory)
    assert len(replay) == REPLAY_BUFFER_MAXLEN, (
        f"Buffer debe estar topado en {REPLAY_BUFFER_MAXLEN}, fue {len(replay)}"
    )
    # Los más viejos deben haberse descartado
    assert replay[0].data == {"i": 20}

    block.set()
    await asyncio.sleep(0.05)
