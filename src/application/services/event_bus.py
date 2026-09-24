"""EventBus — pub/sub en memoria para SSE (Spec-460).

Canales por nombre (`global`, `job:<id>`). Cada canal asigna ids monotónicos a
sus eventos y guarda los últimos N (sin heartbeats) para que un suscriptor que
llega tarde o reconecta con `Last-Event-ID` reciba lo que se perdió.

Uso:
    queue, replay = bus.subscribe("job:123", last_event_id=None)
    try:
        for event in replay:
            yield event.to_sse()
        while True:
            yield (await queue.get()).to_sse()
    finally:
        bus.unsubscribe("job:123", queue)

Todo corre en el event loop: `publish()` es síncrono y no cede el control.
Pensado para un solo proceso (Spec-460 ASSUMPTIONS §1).
"""

import asyncio
from collections import deque

from src.domain.streaming import StreamEvent, StreamEventType

GLOBAL_CHANNEL = "global"
REPLAY_MAXLEN = 200


def job_channel(job_id) -> str:
    return f"job:{job_id}"


class _Channel:
    def __init__(self, replay_maxlen: int) -> None:
        self.next_id = 1
        self.replay: deque[StreamEvent] = deque(maxlen=replay_maxlen)
        self.subscribers: set[asyncio.Queue[StreamEvent]] = set()


class EventBus:
    def __init__(self, replay_maxlen: int = REPLAY_MAXLEN) -> None:
        self._replay_maxlen = replay_maxlen
        self._channels: dict[str, _Channel] = {}

    def _channel(self, name: str) -> _Channel:
        channel = self._channels.get(name)
        if channel is None:
            channel = self._channels[name] = _Channel(self._replay_maxlen)
        return channel

    def publish(self, channel_name: str, event: StreamEvent) -> StreamEvent:
        """Publica en el canal. Devuelve el evento con su `id` asignado.

        Los heartbeats se entregan en vivo, sin id ni lugar en el replay (ruido).
        """
        channel = self._channel(channel_name)
        if event.event != StreamEventType.HEARTBEAT:
            event = event.model_copy(update={"id": channel.next_id})
            channel.next_id += 1
            channel.replay.append(event)
        for queue in list(channel.subscribers):
            queue.put_nowait(event)
        return event

    def subscribe(
        self, channel_name: str, last_event_id: int | None = None
    ) -> tuple[asyncio.Queue[StreamEvent], list[StreamEvent]]:
        """Suscribe al canal. Devuelve `(queue, replay)`.

        `replay` son los eventos guardados con id mayor a `last_event_id`
        (todos si es None). El consumidor drena primero el replay y después la queue.
        """
        channel = self._channel(channel_name)
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        channel.subscribers.add(queue)
        replay = [e for e in channel.replay if last_event_id is None or (e.id or 0) > last_event_id]
        return queue, replay

    def unsubscribe(self, channel_name: str, queue: asyncio.Queue[StreamEvent]) -> None:
        channel = self._channels.get(channel_name)
        if channel is not None:
            channel.subscribers.discard(queue)

    def drop(self, channel_name: str) -> None:
        """Descarta el canal y su replay (limpieza por TTL de jobs terminados)."""
        self._channels.pop(channel_name, None)

    def has_channel(self, channel_name: str) -> bool:
        return channel_name in self._channels
