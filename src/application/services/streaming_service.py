"""StreamingService — adapta execute_full() a un stream de StreamEvent (Spec-201).

Arquitectura: Queue compartida entre productor principal y heartbeat.
Garantiza que los heartbeats se emiten DURANTE la espera del LLM,
no solo entre beats (crítico para conexiones largas con Nginx/Browser).
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from src.application.use_cases.director_use_case import DirectorUseCase
from src.domain.models import Story
from src.domain.streaming import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15  # segundos — no negociable (punto 2 Spec-201)

_SENTINEL = object()


async def stream_story(
    director: DirectorUseCase,
    story: Story,
    story_repo=None,
) -> AsyncGenerator[StreamEvent, None]:
    """Orquesta execute_full() y traduce sus yields a StreamEvent.

    Usa una Queue compartida entre el productor principal y la tarea de heartbeat
    para garantizar que los heartbeats se envíen DURANTE la espera del LLM.

    Flujo de eventos:
        status     → cambios de fase
        beat_start → inicio de cada beat
        beat_done  → beat narrado con content ya normalizado (Normalizer actúa en VozUseCase)
        heartbeat  → cada 15s de inactividad para mantener la conexión viva
        done       → pipeline completo
        error      → cualquier excepción (puede ocurrir a mitad de conexión)
    """
    queue: asyncio.Queue[StreamEvent | object] = asyncio.Queue()
    num_beats = director.prompt_builder.num_beats

    # ── Productor principal ───────────────────────────────────────────────────
    async def _main_producer():
        try:
            if story_repo is not None:
                await story_repo.update_status(story.id, "processing")

            await queue.put(StreamEvent(
                event=StreamEventType.STATUS,
                data={"msg": "Analizando sinopsis y extrayendo anclajes...", "step": "analyst"},
            ))

            beat_number = 0
            async for macro_beat, _journal, _elapsed in director.execute_full(story):
                beat_number += 1

                await queue.put(StreamEvent(
                    event=StreamEventType.BEAT_START,
                    data={
                        "number": beat_number,
                        "type": macro_beat.beat_type.value if macro_beat.beat_type else "",
                    },
                ))

                if beat_number < num_beats:
                    await queue.put(StreamEvent(
                        event=StreamEventType.STATUS,
                        data={
                            "msg": f"Narrando beat {beat_number + 1}/{num_beats}...",
                            "step": "mapper",
                        },
                    ))

                await queue.put(StreamEvent(
                    event=StreamEventType.BEAT_DONE,
                    data={"number": beat_number, "content": macro_beat.content},
                ))

            if story_repo is not None:
                await story_repo.update_status(story.id, "completed")

            await queue.put(StreamEvent(
                event=StreamEventType.DONE,
                data={"story_id": str(story.id), "total_beats": beat_number},
            ))

        except Exception as exc:
            logger.exception("[STREAMING] Error durante pipeline")
            if story_repo is not None:
                try:
                    await story_repo.update_status(story.id, "failed")
                except Exception:
                    pass
            await queue.put(StreamEvent(
                event=StreamEventType.ERROR,
                data={"msg": str(exc)},
            ))
        finally:
            await queue.put(_SENTINEL)

    # ── Heartbeat producer — se ejecuta en paralelo con el productor principal ─
    async def _heartbeat_producer(stop: asyncio.Event):
        """Inyecta un heartbeat cada HEARTBEAT_INTERVAL segundos hasta que stop se activa.

        Al correr como tarea independiente en el mismo event loop,
        los heartbeats se emiten DURANTE la espera del LLM, no solo entre beats.
        """
        while not stop.is_set():
            try:
                await asyncio.wait_for(
                    asyncio.shield(stop.wait()),
                    timeout=HEARTBEAT_INTERVAL,
                )
            except asyncio.TimeoutError:
                if not stop.is_set():
                    await queue.put(StreamEvent(
                        event=StreamEventType.HEARTBEAT,
                        data={"alive": True},
                    ))

    stop_event = asyncio.Event()
    main_task = asyncio.create_task(_main_producer())
    hb_task   = asyncio.create_task(_heartbeat_producer(stop_event))

    try:
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            yield item  # type: ignore[misc]
    finally:
        stop_event.set()
        main_task.cancel()
        hb_task.cancel()
        for task in (main_task, hb_task):
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
