"""StreamingService — adapta execute_full() a un stream de StreamEvent (Spec-201).

Arquitectura: Queue compartida entre productor principal y heartbeat.
Garantiza que los heartbeats se emiten DURANTE la espera del LLM,
no solo entre beats (crítico para conexiones largas con Nginx/Browser).
"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from src.application.services.observability_service import observability
from src.application.use_cases.director_use_case import DirectorUseCase
from src.domain.models import Story, StoryStatus
from src.domain.streaming import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15  # segundos — no negociable (punto 2 Spec-201)

_SENTINEL = object()


async def stream_story(
    director: DirectorUseCase,
    story: Story,
    story_repo=None,
    beat_repo=None,
    export_service=None,
) -> AsyncGenerator[StreamEvent, None]:
    """Orquesta execute_full() y traduce sus yields a StreamEvent.

    Usa una Queue compartida entre el productor principal y la tarea de heartbeat
    para garantizar que los heartbeats se envíen DURANTE la espera del LLM.

    Flujo de eventos:
        status     → cambios de fase
        beat_start → inicio de cada beat
        beat_done  → beat persistido en DB + emitido al cliente
        heartbeat  → cada 15s de inactividad para mantener la conexión viva
        done       → pipeline completo (incluye file_path si se exportó MD)
        error      → cualquier excepción (puede ocurrir a mitad de conexión)
    """
    queue: asyncio.Queue[StreamEvent | object] = asyncio.Queue()
    num_beats = director.prompt_builder.num_beats

    # ── Productor principal ───────────────────────────────────────────────────
    async def _main_producer():
        try:
            # Spec-220: la limpieza canónica de artefactos vive en update_story_status
            # (Spec-216 Slice A). La idempotencia del SSE la garantiza StreamSessionManager:
            # un solo productor por story_id, las conexiones extra se atan a la sesión
            # existente. Sin necesidad de salvaguardas defensivas acá.
            if story_repo is not None:
                await story_repo.update_status(story.id, "processing")

            await queue.put(
                StreamEvent(
                    event=StreamEventType.STATUS,
                    data={"msg": "Analizando sinopsis y extrayendo anclajes...", "step": "analyst"},
                )
            )

            beat_number = 0
            beats_collected = []
            async for macro_beat, _journal, _elapsed in director.execute_full(story):
                beat_number += 1
                beats_collected.append(macro_beat)

                await queue.put(
                    StreamEvent(
                        event=StreamEventType.BEAT_START,
                        data={
                            "number": beat_number,
                            "type": macro_beat.beat_type.value if macro_beat.beat_type else "",
                        },
                    )
                )

                # Persistir beat y journal en DB antes de emitir al cliente
                if beat_repo is not None:
                    await beat_repo.save(macro_beat, story.id)
                if story_repo is not None and _journal is not None:
                    await story_repo.save_journal(story.id, _journal, beat_number)

                if beat_number < num_beats:
                    await queue.put(
                        StreamEvent(
                            event=StreamEventType.STATUS,
                            data={
                                "msg": f"Narrando beat {beat_number + 1}/{num_beats}...",
                                "step": "mapper",
                            },
                        )
                    )

                await queue.put(
                    StreamEvent(
                        event=StreamEventType.BEAT_DONE,
                        data={"number": beat_number, "content": macro_beat.content},
                    )
                )

            if story_repo is not None:
                await story_repo.update_status(story.id, StoryStatus.COMPLETED.value)
                logger.info(f"[STREAM] Pipeline finalizado con éxito | Story: {story.id}")
                observability.record(
                    category="generation",
                    message=f"Generación completa: '{story.title}'",
                    type="success",
                    story_id=str(story.id),
                    story_title=story.title,
                )

            # Exportar MD y persistir file_path
            file_path = None
            if export_service is not None and beats_collected:
                try:
                    file_path = await export_service.export(story, beats_collected)
                    if story_repo is not None and file_path:
                        await story_repo.update_file_path(story.id, file_path)
                except Exception:
                    logger.exception("[STREAMING] Error al exportar MD")

            await queue.put(
                StreamEvent(
                    event=StreamEventType.DONE,
                    data={
                        "story_id": str(story.id),
                        "total_beats": beat_number,
                        "file_path": file_path,
                    },
                )
            )

        except asyncio.CancelledError:
            if story_repo is not None:
                try:
                    await story_repo.update_status(story.id, "failed")
                except Exception:
                    pass
            raise
        except Exception as exc:
            logger.exception("[STREAMING] Error durante pipeline")
            observability.record(
                category="generation",
                message=f"Error en generación: {str(exc)}",
                type="error",
                story_id=str(story.id),
                story_title=story.title,
            )
            if story_repo is not None:
                try:
                    await story_repo.update_status(story.id, "failed")
                except Exception:
                    pass
            await queue.put(
                StreamEvent(
                    event=StreamEventType.ERROR,
                    data={"msg": str(exc)},
                )
            )
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
                    await queue.put(
                        StreamEvent(
                            event=StreamEventType.HEARTBEAT,
                            data={"alive": True},
                        )
                    )

    stop_event = asyncio.Event()
    main_task = asyncio.create_task(_main_producer())
    hb_task = asyncio.create_task(_heartbeat_producer(stop_event))

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
