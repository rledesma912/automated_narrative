"""Tests de integración del StreamSessionManager con escenarios end-to-end (Spec-220 Slice C).

Validan la coordinación productor único / N consumidores que el endpoint del SSE
implementa. NO usan HTTP ni SQLite — el productor se simula con un async generator
con timing realista. La integración HTTP se valida con smoke manual (CA5 del spec).

Esta capa de tests cubre los criterios CA3, CA4, CA6 y CA7 del spec.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest

from src.application.services.stream_session_manager import StreamSessionManager
from src.domain.streaming import StreamEvent, StreamEventType


def _evt(kind: StreamEventType, data: dict | None = None) -> StreamEvent:
    return StreamEvent(event=kind, data=data or {})


@pytest.fixture
def manager() -> StreamSessionManager:
    return StreamSessionManager()


async def _drain(queue: asyncio.Queue[StreamEvent], timeout: float = 2.0) -> list[StreamEvent]:
    """Drena la queue hasta recibir DONE o ERROR (o timeout)."""
    out: list[StreamEvent] = []
    try:
        while True:
            evt = await asyncio.wait_for(queue.get(), timeout=timeout)
            out.append(evt)
            if evt.event in (StreamEventType.DONE, StreamEventType.ERROR):
                break
    except asyncio.TimeoutError:
        pass
    return out


# ── CA3 ──────────────────────────────────────────────────────────────────────
async def test_two_concurrent_clients_receive_same_events(manager: StreamSessionManager):
    """Cliente A y B atachados al mismo story_id reciben los mismos beats.

    Verifica que UN solo productor emite y ambos consumidores ven la misma secuencia.
    """
    factory_calls: list[int] = []
    pipeline_events = [
        _evt(StreamEventType.STATUS, {"msg": "anchors"}),
        _evt(StreamEventType.BEAT_START, {"number": 1}),
        _evt(StreamEventType.BEAT_DONE, {"number": 1, "content": "b1"}),
        _evt(StreamEventType.BEAT_START, {"number": 2}),
        _evt(StreamEventType.BEAT_DONE, {"number": 2, "content": "b2"}),
        _evt(StreamEventType.DONE, {"total_beats": 2}),
    ]

    def factory() -> AsyncIterator[StreamEvent]:
        factory_calls.append(1)

        async def _gen() -> AsyncIterator[StreamEvent]:
            for e in pipeline_events:
                await asyncio.sleep(0.01)
                yield e

        return _gen()

    # A y B se atachan casi simultáneamente
    queue_a, _ = await manager.attach("s1", factory)
    queue_b, _ = await manager.attach("s1", factory)

    events_a, events_b = await asyncio.gather(_drain(queue_a), _drain(queue_b))

    assert len(factory_calls) == 1, "factory debe ejecutarse 1 sola vez (CA3)"
    assert [e.event for e in events_a] == [e.event for e in pipeline_events]
    assert [e.event for e in events_b] == [e.event for e in pipeline_events]
    # Mismos payloads
    assert [e.data for e in events_a] == [e.data for e in events_b]


# ── CA4 ──────────────────────────────────────────────────────────────────────
async def test_late_client_receives_replay_buffer(manager: StreamSessionManager):
    """Cliente B llega después de beat 2; recibe replay [b1, b2] + eventos en vivo."""
    cliente_b_listo = asyncio.Event()
    pipeline_events = [
        _evt(StreamEventType.BEAT_START, {"number": 1}),
        _evt(StreamEventType.BEAT_DONE, {"number": 1}),
        _evt(StreamEventType.BEAT_START, {"number": 2}),
        _evt(StreamEventType.BEAT_DONE, {"number": 2}),
        # Pausa hasta que B se atache
        _evt(StreamEventType.BEAT_START, {"number": 3}),
        _evt(StreamEventType.BEAT_DONE, {"number": 3}),
        _evt(StreamEventType.DONE, {"total_beats": 3}),
    ]

    def factory() -> AsyncIterator[StreamEvent]:
        async def _gen() -> AsyncIterator[StreamEvent]:
            # Primeros 4 eventos
            for e in pipeline_events[:4]:
                await asyncio.sleep(0.01)
                yield e
            # Esperar a que el cliente B se atache antes de emitir el resto
            await cliente_b_listo.wait()
            for e in pipeline_events[4:]:
                await asyncio.sleep(0.01)
                yield e

        return _gen()

    # Cliente A se atacha primero
    queue_a, replay_a = await manager.attach("s1", factory)
    assert replay_a == []  # primer cliente, sin replay

    # Esperar a que se emitan los primeros 4 eventos
    await asyncio.sleep(0.1)

    # Cliente B se atacha tarde
    queue_b, replay_b = await manager.attach("s1", factory)
    cliente_b_listo.set()  # destrabar productor

    # B debe recibir replay con los 4 primeros eventos
    assert len(replay_b) == 4
    assert [e.event for e in replay_b] == [
        StreamEventType.BEAT_START,
        StreamEventType.BEAT_DONE,
        StreamEventType.BEAT_START,
        StreamEventType.BEAT_DONE,
    ]

    # B también recibe los eventos en vivo posteriores
    live_b = await _drain(queue_b)
    assert [e.event for e in live_b] == [
        StreamEventType.BEAT_START,
        StreamEventType.BEAT_DONE,
        StreamEventType.DONE,
    ]

    # Limpieza
    await _drain(queue_a)


# ── CA7 ──────────────────────────────────────────────────────────────────────
async def test_session_cleaned_up_after_done(manager: StreamSessionManager):
    """Tras DONE + detach del último consumer, la sesión se elimina del registry."""

    def factory() -> AsyncIterator[StreamEvent]:
        async def _gen() -> AsyncIterator[StreamEvent]:
            yield _evt(StreamEventType.STATUS, {"msg": "go"})
            yield _evt(StreamEventType.DONE)

        return _gen()

    queue, _ = await manager.attach("s1", factory)
    await _drain(queue)

    assert manager.is_active("s1"), "Sesión sigue activa hasta detach del último consumer"

    await manager.detach("s1", queue)
    assert not manager.is_active("s1"), "Sesión eliminada tras último detach (CA7)"


# ── CA6 (preventivo) ─────────────────────────────────────────────────────────
async def test_disconnect_does_not_kill_producer_if_other_consumers_remain(
    manager: StreamSessionManager,
):
    """Cliente A se desconecta a mitad; cliente B sigue recibiendo eventos.

    Garantiza que la generación valiosa no se aborta por desconexión parcial.
    """
    pipeline_events = [
        _evt(StreamEventType.BEAT_START, {"number": 1}),
        _evt(StreamEventType.BEAT_DONE, {"number": 1}),
        _evt(StreamEventType.BEAT_START, {"number": 2}),
        _evt(StreamEventType.BEAT_DONE, {"number": 2}),
        _evt(StreamEventType.DONE, {"total_beats": 2}),
    ]

    def factory() -> AsyncIterator[StreamEvent]:
        async def _gen() -> AsyncIterator[StreamEvent]:
            for e in pipeline_events:
                await asyncio.sleep(0.02)
                yield e

        return _gen()

    queue_a, _ = await manager.attach("s1", factory)
    queue_b, _ = await manager.attach("s1", factory)

    # A consume 2 eventos y se "desconecta"
    _ = await asyncio.wait_for(queue_a.get(), timeout=1.0)
    _ = await asyncio.wait_for(queue_a.get(), timeout=1.0)
    await manager.detach("s1", queue_a)

    # B sigue recibiendo el resto del pipeline hasta DONE
    events_b = await _drain(queue_b)
    assert events_b[-1].event == StreamEventType.DONE
    assert sum(1 for e in events_b if e.event == StreamEventType.BEAT_DONE) == 2

    await manager.detach("s1", queue_b)
    assert not manager.is_active("s1")


# ── Bonus: producer error se propaga como evento ERROR ───────────────────────
async def test_producer_exception_emits_stream_error(manager: StreamSessionManager):
    """Si el productor crashea, los consumidores reciben un evento ERROR (no excepción cruda)."""

    def factory() -> AsyncIterator[StreamEvent]:
        async def _gen() -> AsyncIterator[StreamEvent]:
            yield _evt(StreamEventType.STATUS, {"msg": "starting"})
            raise RuntimeError("boom")

        return _gen()

    queue, _ = await manager.attach("s1", factory)
    events = await _drain(queue)

    assert events[-1].event == StreamEventType.ERROR
    assert "boom" in str(events[-1].data)
