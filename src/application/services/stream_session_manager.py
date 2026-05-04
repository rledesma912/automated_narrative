"""StreamSessionManager — broadcaster idempotente para SSE (Spec-220).

Garantiza UN único productor (`stream_story()`) por `story_id` simultáneo y
distribuye los eventos a N consumidores HTTP. Resuelve la falsa idempotencia
de `stream_router.py:48-51` y bloquea la doble ejecución del pipeline LLM
cuando dos clientes se conectan al mismo `story_id`.

Uso:
    queue, replay = await manager.attach(story_id, producer_factory)
    try:
        for event in replay:
            yield event.to_sse()
        while True:
            event = await queue.get()
            yield event.to_sse()
            if event.event in (DONE, ERROR):
                break
    finally:
        await manager.detach(story_id, queue)

`producer_factory` es una callable sin args que devuelve un `AsyncIterator[StreamEvent]`
(típicamente envuelve `stream_story(director, story, ...)`). Solo se invoca la primera
vez para un `story_id`; las conexiones posteriores se atan al productor existente y
reciben el `replay_buffer` (últimos 50 eventos no-heartbeat) antes del flujo en vivo.
"""

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Callable

from src.domain.streaming import StreamEvent, StreamEventType

REPLAY_BUFFER_MAXLEN = 50


class StreamSession:
    """Sesión de streaming asociada a un único `story_id`. Un productor, N consumidores."""

    def __init__(self, story_id: str) -> None:
        self.story_id = story_id
        self.producer_task: asyncio.Task | None = None
        self.consumers: set[asyncio.Queue[StreamEvent]] = set()
        self.replay_buffer: deque[StreamEvent] = deque(maxlen=REPLAY_BUFFER_MAXLEN)
        self.done_event: asyncio.Event = asyncio.Event()

    def start_producer(self, producer_factory: Callable[[], AsyncIterator[StreamEvent]]) -> None:
        """Lanza el productor único como Task. Solo se debe llamar una vez por sesión."""

        async def _runner() -> None:
            try:
                async for event in producer_factory():
                    await self.broadcast(event)
            except Exception as exc:  # noqa: BLE001
                err = StreamEvent(
                    event=StreamEventType.ERROR,
                    data={"msg": f"Productor falló: {exc}"},
                )
                await self.broadcast(err)
            finally:
                # Aseguramos done_event aunque el productor termine sin emitir DONE/ERROR.
                self.done_event.set()

        self.producer_task = asyncio.create_task(_runner())

    async def broadcast(self, event: StreamEvent) -> None:
        """Distribuye un evento a todos los consumidores y al replay buffer.

        - HEARTBEAT se distribuye en vivo pero NO se persiste en el buffer (ruido).
        - DONE/ERROR marcan `done_event` para que `detach()` pueda limpiar la sesión.
        """
        if event.event != StreamEventType.HEARTBEAT:
            self.replay_buffer.append(event)
        if event.event in (StreamEventType.DONE, StreamEventType.ERROR):
            self.done_event.set()
        for queue in list(self.consumers):
            queue.put_nowait(event)


class StreamSessionManager:
    """Registry de sesiones por `story_id`. Pensado para usarse como singleton del módulo."""

    def __init__(self) -> None:
        self._sessions: dict[str, StreamSession] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def attach(
        self,
        story_id: str,
        producer_factory: Callable[[], AsyncIterator[StreamEvent]],
    ) -> tuple[asyncio.Queue[StreamEvent], list[StreamEvent]]:
        """Atacha un consumidor a la sesión. Si no existe, la crea y arranca el productor.

        Returns:
            (queue, replay_snapshot). El consumidor debe drainar primero el replay
            y después la queue.
        """
        async with self._lock:
            session = self._sessions.get(story_id)
            if session is None:
                session = StreamSession(story_id)
                self._sessions[story_id] = session
                session.start_producer(producer_factory)
            queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
            session.consumers.add(queue)
            replay = list(session.replay_buffer)
        return queue, replay

    async def detach(self, story_id: str, queue: asyncio.Queue[StreamEvent]) -> None:
        """Desuscribe un consumidor. Limpia la sesión si fue el último y el productor terminó."""
        async with self._lock:
            session = self._sessions.get(story_id)
            if session is None:
                return
            session.consumers.discard(queue)
            if session.done_event.is_set() and not session.consumers:
                del self._sessions[story_id]

    def is_active(self, story_id: str) -> bool:
        return story_id in self._sessions


manager = StreamSessionManager()
