# Spec-220: Stream Broadcaster Idempotente y MODO MONITOR

## Estado
IMPLEMENTADO — T1-T5 aplicados; T6 verificación automática completa. CA3, CA4, CA6, CA7, CA8 verificados via tests; CA1, CA2, CA5 verificados con smoke manual (2026-05-04) con frontend + 2 pestañas.

---

## Objetivo

Reemplazar el endpoint SSE actual (`stream_router.py:27-76`) por una arquitectura broadcaster que garantice **un único pipeline de generación por `story_id` simultáneo** y permita que múltiples clientes se conecten/observen el mismo stream sin disparar pipelines duplicados ni destruir artefactos. En el frontend, introducir un **MODO MONITOR** en la sala que se ata como observador a una generación en curso (sin disparar nada).

Resultado: la pestaña B que hace "Ver avance" durante una generación activa ve los mismos eventos en vivo que la pestaña A, sin que se duplique nada en backend.

---

## Problema

Dos bugs encadenados detectados en el flujo "iniciar regeneración + abrir nueva pestaña":

### Bug 1 — UI: `start-panel` se muestra en sala con status=processing

`streaming-room.ejs:13` agrupa en un único bloque "MODO SSE" dos casos opuestos: (i) "voy a iniciar una generación" y (ii) "ya hay una corriendo, vine a mirar". Ambos muestran el botón "Iniciar generación", confundiendo al usuario.

### Bug 2 — Backend: `stream_router.py:48-51` declara idempotencia que no implementa

```python
# Punto 3 — Idempotencia: si ya está en processing, permitir reconexión para ver progreso
if story.status.value == "processing":
    logger.info(...)  # solo loguea
    # Continuar para permitir que el navegador se conecte al stream existente  ← falso
```

El código sigue hacia abajo y crea **un nuevo `stream_story()`** con su propio productor LLM. Combinado con la salvaguarda redundante de `streaming_service.py:56-68` (que borra artefactos al recibir un stream con status `processing`/`completed`/`failed`), una segunda conexión al mismo `story_id`:

1. Borra los beats/journal/anchors **de la generación que está corriendo**.
2. Resetea el `.md` físico.
3. Lanza un segundo pipeline LLM en paralelo, escribiendo al mismo `story_id`.
4. Doble persistencia, condiciones de carrera, integridad rota.

Spec-201 punto 3 (idempotencia) está pendiente desde el origen del SSE.

---

## Decisiones de diseño cerradas

| # | Decisión | Justificación |
|---|---|---|
| **D1** | Singleton `StreamSessionManager` que mapea `story_id → StreamSession`. Patrón idéntico a `ObservabilityService` (`_instance` + `__new__`). | Reutiliza patrón ya validado en el proyecto. |
| **D2** | Cada `StreamSession` tiene **un único productor** (`stream_story()`) y N consumidores. El primer cliente que se conecta arranca el productor; los demás se atan vía `asyncio.Queue` propia. | Garantiza un solo pipeline LLM por historia. |
| **D3** | **Replay buffer**: la sesión guarda los últimos N eventos emitidos (excluyendo `heartbeat`). Cliente que se suma tarde recibe el catch-up sintético antes del flujo en vivo. | Permite que pestaña B vea los beats anteriores sin perder contexto. N = 50 (suficiente para 5 beats × ~3 eventos cada uno + holgura). |
| **D4** | La sesión se elimina del manager cuando emite `done`/`error` y todos los consumidores se desuscriben. | Evita leak de memoria. |
| **D5** | `MODO MONITOR` en frontend: cuando `status === 'processing'` y NO viene `?regenerate=1`, la sala renderiza vista monitor (sin start-panel) y abre EventSource (que ahora es seguro gracias al broadcaster). | Resuelve Bug 1 sin polling, ya que Slice B+C habilitan SSE seguro. |
| **D6** | La salvaguarda redundante de `streaming_service.py:56-68` se elimina al final del refactor. Con el broadcaster + idempotencia, no puede haber segunda conexión que la dispare. | Reduce superficie de error futuro. |
| **D7** | Sin breaking changes intermedios: cada slice deja el sistema en estado funcionando. El frontend MODO MONITOR (Slice A) inicialmente usa polling como fallback; al desplegar Slice B+C el polling se reemplaza por EventSource. | Permite mergear/desplegar slices independientes. |

---

## Arquitectura

### Diagrama de componentes

```
                ┌──────────────────────────────────────────┐
                │  HTTP — GET /stories/:id/stream          │
                │  (cliente A, cliente B, cliente C)       │
                └──────┬─────────────┬─────────────┬───────┘
                       ▼             ▼             ▼
              ┌────────────────────────────────────────────┐
              │  stream_router.stream_generation(story_id) │
              │   ↓                                        │
              │   StreamSessionManager.attach(story_id)    │
              │   → returns Queue[StreamEvent] del cliente │
              └──────┬─────────────────────────────────────┘
                     ▼
              ┌─────────────────────────────────────────────┐
              │  StreamSessionManager (singleton)           │
              │  ─────────────────────────────────────────  │
              │  _sessions: dict[story_id → StreamSession]  │
              │                                             │
              │  attach(story_id):                          │
              │    if story_id ∉ _sessions:                 │
              │       create StreamSession                  │
              │       spawn _producer task (1 sola vez)     │
              │    register new consumer Queue              │
              │    return (queue, replay_events)            │
              │                                             │
              │  detach(story_id, queue):                   │
              │    remove consumer; if 0 → cleanup session  │
              └────┬─────────────────────────┬──────────────┘
                   │                         │
                   ▼                         ▼
          ┌────────────────┐       ┌────────────────────────┐
          │ StreamSession  │       │ StreamSession           │
          │  (story_X)     │       │  (story_Y)              │
          │ ─────────────  │       │ ──────────────────────  │
          │ producer_task  │       │ producer_task           │
          │ consumers: [Q1,│       │ consumers: [Q1]         │
          │              Q2│       │ replay_buffer: [...]    │
          │              Q3]       │                         │
          │ replay_buffer  │       └────────────────────────┘
          │ done_event     │
          └───────┬────────┘
                  │ stream_story(...) — productor único
                  ▼
          ┌─────────────────────────────────────┐
          │ Director.execute_full(story)        │
          │ → 5 beats × {mapper + voz + journal}│
          └─────────────────────────────────────┘
```

### Flujo de un evento

```
[Productor único]
  yield event → session.broadcast(event)
                  ├── replay_buffer.append(event)  (skip si HEARTBEAT)
                  └── for queue in consumers:
                          queue.put_nowait(event)

[Consumidor — uno por cliente HTTP]
  while True:
      event = await queue.get()
      yield event.to_sse()
```

### Flujo attach / detach

```
[Cliente A llega]
  attach("story_X")
    sessions["story_X"] no existe
    crea StreamSession + lanza producer_task
    registra queue_A
  cliente A consume queue_A

[Cliente B llega 30s después]
  attach("story_X")
    sessions["story_X"] existe (productor ya corriendo, beat 2/5 emitido)
    registra queue_B
    encola replay_buffer en queue_B (catch-up: beats 1-2)
  cliente B consume queue_B (primero el catch-up, después en vivo)

[Productor emite DONE]
  broadcast(DONE) → todos los consumers reciben
  session.done_event.set()
  consumers detectan DONE → cierran HTTP

[Manager detecta]
  consumers count == 0 → cleanup session
```

---

## Slices (incrementales, sin breaking changes)

### Slice A — Frontend: MODO MONITOR con polling (no rompe nada en backend)

**Objetivo:** resolver Bug 1 (start-panel visible) inmediatamente sin tocar backend. Si el usuario llega a la sala con generación en curso, ve el estado actual + polling cada 5s al status. Esto blinda contra la doble conexión SSE accidental porque NO abre EventSource.

**Archivos:**
- `frontend/src/controllers/stream.controller.ts` — calcula `monitorMode = (storyStatus === 'processing' && !regenerateMode)` y lo pasa al view.
- `frontend/src/views/streaming-room.ejs`:
  - Tres modos en lugar de dos: `MODO LECTURA`, `MODO MONITOR` (nuevo), `MODO SSE` (con submodos REGEN / INICIO según `regenerateMode`).
  - MODO MONITOR: muestra los beats parciales (consume `beats` ya cargados desde DB), badge "GENERANDO", spinner sutil, mensaje "Esta historia se está generando. Esperá a que finalice…". JS arranca `monitorPolling()` que hace `GET /api/v1/stories/:id` cada 5s; cuando detecta `completed`/`failed`, refresca la página.
- `frontend/src/views/gallery.ejs`: opcionalmente cambiar el rótulo "Ver avance" para `processing` por "Ver generación activa" (claridad).

**Sin cambios en backend.** El bug 2 sigue latente pero ya no se dispara desde la UI estándar (porque MODO MONITOR no abre EventSource).

### Slice B — Backend: `StreamSessionManager` singleton

**Objetivo:** introducir el manager + sesión sin todavía cambiar el endpoint. Solo agregar la infraestructura.

**Archivos nuevos:**
- `src/application/services/stream_session_manager.py` con clases:
  - `StreamSession`:
    - `story_id: str`
    - `producer_task: asyncio.Task | None`
    - `consumers: set[asyncio.Queue]`
    - `replay_buffer: deque[StreamEvent]` (maxlen=50, descarta `HEARTBEAT`)
    - `done_event: asyncio.Event`
    - `lock: asyncio.Lock`
    - `broadcast(event)`: append al buffer (filtrando HEARTBEAT) + put a cada consumer (`put_nowait`).
  - `StreamSessionManager` (singleton — patrón `ObservabilityService`):
    - `_sessions: dict[str, StreamSession]`
    - `_lock: asyncio.Lock` (protege creación/borrado)
    - `attach(story_id, producer_factory) → (queue, replay)`: crea sesión si no existe, registra consumer, devuelve queue + snapshot del replay buffer.
    - `detach(story_id, queue)`: remueve consumer; si 0 y `done_event` activo, elimina sesión.
    - `is_active(story_id) → bool`: para introspección (útil en tests + endpoints futuros).

**Sin tocar:** `stream_router.py`, `streaming_service.py`. El manager existe pero nadie lo usa todavía.

**Tests unitarios** (`tests/unit/application/services/test_stream_session_manager.py`):
- `test_attach_creates_session_first_time`
- `test_attach_reuses_existing_session`
- `test_attach_returns_replay_buffer_snapshot`
- `test_detach_removes_consumer`
- `test_detach_cleans_session_when_last_consumer_leaves_after_done`
- `test_broadcast_skips_heartbeat_in_replay_buffer`
- `test_concurrent_attach_creates_only_one_session` (race condition con `asyncio.Lock`)

### Slice C — Backend: endpoint usa el manager

**Objetivo:** cablear `stream_router.py` al manager. Mantener compatibilidad: el primer cliente arranca el productor, los siguientes se atan al mismo. Eliminar la falsa idempotencia.

**Archivos:**
- `src/presentation/routers/stream_router.py`:
  - `stream_generation(story_id)` ahora:
    1. Valida que la story existe (404 si no).
    2. Define `producer_factory` que construye `director`/`prompt_builder`/`normalizer`/etc. y devuelve `stream_story(...)`.
    3. `queue, replay = await manager.attach(story_id, producer_factory)`.
    4. `event_generator()` primero yield-ea el `replay`, después drain de la `queue`.
    5. Al cerrarse la conexión (cliente desconecta o stream termina), `await manager.detach(story_id, queue)`.
  - Elimina las líneas 48-51 del comentario falso de idempotencia.
- `src/application/services/streaming_service.py`:
  - El productor ahora es construido por `producer_factory` desde el manager. La función `stream_story()` se conserva tal cual; solo cambia quién la llama.
  - **Mantener** la salvaguarda redundante (líneas 56-68) en este slice — se eliminará en Slice E.

**Tests integración** (`tests/integration/test_stream_broadcaster.py` con MockLLMAdapter):
- `test_two_concurrent_clients_receive_same_events`
- `test_late_client_receives_replay_buffer`
- `test_session_cleaned_up_after_done`
- `test_disconnect_does_not_kill_producer_if_other_consumers_remain`

### Slice D — Frontend: MODO MONITOR usa EventSource (no más polling)

**Objetivo:** ahora que Slice B+C garantizan que reconectar es seguro, MODO MONITOR abre EventSource en vez de hacer polling. UX en vivo.

**Archivos:**
- `frontend/src/views/streaming-room.ejs`:
  - MODO MONITOR ahora llama a `attachToStream()` (nueva función JS) que:
    1. Reusa `startStream()` (que abre `EventSource(STREAM_URL)`).
    2. Pero salta el `start-panel` y muestra log directamente.
  - La función `monitorPolling()` introducida en Slice A se elimina.

**Sin cambios en backend.**

### Slice E — Cleanup: eliminar salvaguarda redundante

**Objetivo:** con el broadcaster idempotente, la salvaguarda de `streaming_service.py:56-68` ya no puede dispararse desde una segunda conexión SSE. La limpieza canónica vive en `update_story_status` (Spec-216 Slice A) y se ejecuta una sola vez antes del primer `stream_story()`.

**Archivos:**
- `src/application/services/streaming_service.py`:
  - Eliminar el bloque `if story_repo is not None: ... if story.status.value in ("completed", "failed", "processing"): ...` (líneas 51-67).
  - Mantener `await story_repo.update_status(story.id, "processing")` en línea 68 (transición segura, idempotente).

**Tests de regresión:**
- `test_regeneration_still_clears_artifacts_via_endpoint` — la limpieza canónica del PATCH endpoint sigue funcionando.
- `test_no_double_pipeline_on_concurrent_attach` — con el manager, dos requests simultáneos al mismo story_id arrancan UN productor.

---

## Tareas

### T1 — Slice A: Frontend MODO MONITOR con polling

- **Acceptance:**
  - `stream.controller.ts::streamingRoomPage` calcula `monitorMode = (storyStatus === "processing" && !regenerateMode)` y lo pasa al render context.
  - `streaming-room.ejs` reorganiza el árbol condicional en 3 ramas:
    - MODO LECTURA: `!processing && !regenerateMode && !monitorMode`
    - MODO MONITOR: `monitorMode === true`
    - MODO SSE: `regenerateMode === true || (status === draft/pending y showStartButton)`
  - MODO MONITOR muestra: beats parciales del DB, spinner sutil, badge "GENERANDO", mensaje "Esta historia se está generando. Esperá a que finalice…", **sin** start-panel ni botón "Iniciar".
  - JS `monitorPolling()` hace `setInterval(() => fetch GET /api/v1/stories/:id, 5000)`. Cuando `status` cambia a `completed`/`failed`, llama `window.location.reload()`.
  - `gallery.ejs`: para `processing`, rótulo del link cambia a "Ver generación activa" (claridad).
- **Verify:** smoke 2 pestañas — A inicia regeneración, B navega a galería + click en "Ver avance" → ve MODO MONITOR; DevTools muestra `GET /api/v1/stories/:id` cada 5s; **0 EventSource** en pestaña B; al terminar generación, B recarga.
- **Files:** `frontend/src/controllers/stream.controller.ts`, `frontend/src/views/streaming-room.ejs`, `frontend/src/views/gallery.ejs`.

### T2 — Slice B: `StreamSessionManager` singleton + tests unitarios

- **Acceptance:**
  - Archivo nuevo `src/application/services/stream_session_manager.py` con:
    - Clase `StreamSession`: `story_id`, `producer_task`, `consumers: set[asyncio.Queue]`, `replay_buffer: deque(maxlen=50)`, `done_event: asyncio.Event`.
      - Método `broadcast(event)`: skip HEARTBEAT del buffer; `put_nowait` a cada consumer; si `event.event in (DONE, ERROR)` set `done_event`.
    - Clase `StreamSessionManager` (singleton patrón `ObservabilityService` + `_lock: asyncio.Lock`):
      - `attach(story_id, producer_factory) → (queue, replay_snapshot)`: crea sesión bajo lock si no existe + lanza `producer_task`; registra nuevo queue; devuelve `(queue, list(replay_buffer))`.
      - `detach(story_id, queue)`: remueve queue; si `done_event.is_set() and len(consumers) == 0`, elimina del dict.
      - `is_active(story_id) → bool`.
    - Instancia singleton al final del módulo: `manager = StreamSessionManager()`.
  - 7 tests unitarios pasan (ver sección Tests del SPECIFY).
- **Verify:** `pytest tests/unit/application/services/test_stream_session_manager.py -v` → 7/7 PASSED.
- **Files:** `src/application/services/stream_session_manager.py` (nuevo), `tests/unit/application/services/test_stream_session_manager.py` (nuevo).

### T3 — Slice C: Endpoint cablea al manager + tests integración

- **Acceptance:**
  - `stream_router.stream_generation`:
    1. Valida story (404).
    2. Define `producer_factory()` que construye `LLMFactory.get_provider()`, `PromptBuilder()`, `ResponseNormalizer()`, `SQLBeatRepository()`, `ExportService()`, `DirectorUseCase(...)` y devuelve `stream_story(director, story, story_repo, beat_repo, export_service)`.
    3. `queue, replay = await manager.attach(story_id, producer_factory)`.
    4. `event_generator()` yield-ea primero el `replay`, después drain de la queue.
    5. En `finally`/cleanup, `await manager.detach(story_id, queue)`.
    6. Eliminar líneas 48-51 (comentario falso de idempotencia).
  - `streaming_service.stream_story` queda intacto (mantiene salvaguarda Slice E pendiente).
  - 4 tests integración pasan (ver sección Tests del SPECIFY).
  - Setup nuevo de fixtures SSE en `tests/integration/conftest.py` o inline (httpx.AsyncClient + lifespan).
- **Verify:** `pytest tests/integration/test_stream_broadcaster.py -v` → 4/4 PASSED. Smoke 2 pestañas: log backend muestra **un solo** "Iniciando generación" para el `story_id`.
- **Files:** `src/presentation/routers/stream_router.py`, `tests/integration/test_stream_broadcaster.py` (nuevo), opcional `tests/integration/conftest.py`.

### T4 — Slice D: Frontend MODO MONITOR usa EventSource real

- **Acceptance:**
  - En `streaming-room.ejs`, MODO MONITOR llama nueva función JS `attachToStream()` que:
    - Oculta start-panel (no aplica acá pero por seguridad).
    - Muestra log-container y spinner sutil.
    - Llama `startStream()` (que abre `EventSource(STREAM_URL)`).
  - Función `monitorPolling()` (introducida en T1) se elimina junto con su `setInterval` y handlers.
  - HTML del MODO MONITOR no muestra start-panel ni el panel "¿Listo para…?".
- **Verify:** smoke 2 pestañas — A inicia regeneración, B abre sala vía MODO MONITOR. B muestra `beat_done` en vivo a la par que A. DevTools en B: 1 EventSource abierto. Backend log: **1 solo** pipeline.
- **Files:** `frontend/src/views/streaming-room.ejs`.

### T5 — Slice E: Eliminar salvaguarda redundante

- **Acceptance:**
  - En `src/application/services/streaming_service.py::_main_producer`, eliminar el bloque (~líneas 51-67):
    ```python
    if story_repo is not None:
        if story.status.value in ("completed", "failed", "processing"):
            observability.record(...)
            if story.file_path:
                md_file.unlink(missing_ok=True)
                await story_repo.update_file_path(story.id, None)
            await story_repo.clear_story_artifacts(story.id)
        await story_repo.update_status(story.id, "processing")
    ```
  - Mantener únicamente la transición `await story_repo.update_status(story.id, "processing")` como afirmación de estado (idempotente si ya está processing).
  - Comentario explicativo: "Limpieza canónica vive en update_story_status (Spec-216). Idempotencia garantizada por StreamSessionManager (Spec-220)."
- **Verify:**
  - `pytest tests -v` (full suite) → mismo nivel de passing que pre-Slice E.
  - Smoke regen completo: pestaña A inicia regen, status pasa a processing, beats viejos borrados (vía PATCH), pipeline completa, MD generado.
  - Smoke multi-cliente: pestaña A en SSE + pestaña B en MODO MONITOR (T4) → artefactos NO se borran al sumarse B.
- **Files:** `src/application/services/streaming_service.py`.

### T6 — Verificación integral CA1-CA8

- **Acceptance:** los 8 criterios del SPECIFY pasan.
- **Verify:**
  - **CA1:** pestaña B en sala con processing → no aparece start-panel.
  - **CA2:** tras T1 (no aplica tras T4), polling activo, 0 EventSource. *Nota: tras T4 este criterio queda obsoleto, reemplazado por CA5.*
  - **CA3:** dos httpx SSE concurrentes → 1 solo `execute_full` (test integración).
  - **CA4:** late client recibe replay buffer (test integración).
  - **CA5:** pestaña B ve `beat_done` en vivo (smoke).
  - **CA6:** 2 streams al mismo story_id no borran artefactos (test regresión).
  - **CA7:** `manager.is_active(story_id) == False` tras DONE + 0 consumers.
  - **CA8:** `pytest tests -v` mismo nivel que pre-Spec.
- **Files:** ninguno (verificación).

---

## Tests

### Unitarios (`tests/unit/application/services/test_stream_session_manager.py`)

```python
async def test_attach_creates_session_first_time():
    mgr = StreamSessionManager()
    factory_calls = []
    def factory(): factory_calls.append(1); return _empty_async_gen()
    queue, replay = await mgr.attach("s1", factory)
    assert len(factory_calls) == 1
    assert mgr.is_active("s1")

async def test_attach_reuses_existing_session():
    # Segundo attach al mismo story_id NO invoca el factory de nuevo.

async def test_attach_returns_replay_buffer_snapshot():
    # Tras emitir 3 eventos, un cliente nuevo recibe esos 3 antes del flujo en vivo.

async def test_detach_removes_consumer():
    # Después de detach, broadcast no encola en esa queue.

async def test_detach_cleans_session_when_last_consumer_leaves_after_done():
    # Cleanup solo cuando done_event && consumers vacíos.

async def test_broadcast_skips_heartbeat_in_replay_buffer():
    # Heartbeat se distribuye pero NO va al buffer de replay.

async def test_concurrent_attach_creates_only_one_session():
    # asyncio.gather([mgr.attach(...) x10]) → factory invocado 1 sola vez.
```

### Integración (`tests/integration/test_stream_broadcaster.py`)

```python
async def test_two_concurrent_clients_receive_same_events(client_a, client_b):
    # Ambos httpx.AsyncClient se conectan al endpoint con el mismo story_id.
    # Mock LLM emite 5 beats. Ambos clientes reciben los 5 beat_done.

async def test_late_client_receives_replay_buffer():
    # Cliente A se conecta, recibe 2 beat_done, cliente B llega ahora,
    # debe recibir el replay [b1, b2] antes del beat 3.

async def test_session_cleaned_up_after_done():
    # Tras DONE, manager.is_active(story_id) == False.

async def test_disconnect_does_not_kill_producer_if_other_consumers_remain():
    # Cliente A se desconecta a mitad del beat 3, cliente B sigue recibiendo.
```

---

## Criterios de Aceptación

| # | Criterio | Verificación |
|---|---|---|
| **CA1** | Pestaña B abre `/generar/stream/:id` con `status=processing` → no aparece start-panel; muestra MODO MONITOR | Smoke 2 pestañas |
| **CA2** | Tras Slice A, MODO MONITOR no abre EventSource; usa polling | DevTools Network |
| **CA3** | Tras Slice C, dos requests SSE concurrentes al mismo story_id ejecutan **un solo** `director.execute_full` | Log backend + test integración |
| **CA4** | Cliente que se conecta tarde recibe los eventos previos (replay buffer) antes del flujo en vivo | Test integración |
| **CA5** | Tras Slice D, pestaña B ve `beat_done` en vivo a medida que se generan | Smoke 2 pestañas + DevTools |
| **CA6** | Tras Slice E, abrir 2 streams al mismo `story_id` no borra los artefactos del primero | Test regresión |
| **CA7** | `StreamSessionManager.is_active(story_id)` se vuelve `False` tras emitir `DONE` y todos los consumers desconectan | Test integración |
| **CA8** | Toda la suite `pytest tests -v` pasa | CI |

---

## Riesgos

| # | Riesgo | Probabilidad | Mitigación |
|---|---|---|---|
| **R1** | Race condition en `attach` cuando dos clientes llegan a la vez al primer pedido para un `story_id` | Media | `asyncio.Lock` en el manager protege la creación de la sesión (test `test_concurrent_attach_creates_only_one_session`) |
| **R2** | `Queue.put_nowait` puede fallar si un consumidor lento llena su cola | Baja | Cola sin `maxsize` (default ilimitada); si surge problema en producción, usar `Queue(maxsize=N)` con política drop-oldest |
| **R3** | El productor sigue corriendo aunque no quede ningún consumidor (cliente A se desconecta antes del DONE) | Aceptable | Decisión: no cancelar el productor por desconexión total (la generación es valiosa, debe completarse y persistir). Solo se limpia la sesión tras DONE + 0 consumers. |
| **R4** | El replay buffer crece sin límite si muchas historias quedan abiertas | Baja | `deque(maxlen=50)` por sesión + cleanup tras DONE |
| **R5** | Tests integración de SSE pueden ser flaky por timing | Media | Usar `MockLLMAdapter` con `await asyncio.sleep(0)` entre beats; `asyncio.wait_for` con timeout generoso |
| **R6** | Eliminar la salvaguarda redundante (Slice E) deja sin red al caso "stream iniciado sin pasar por PATCH endpoint" | Baja | Verificar en Slice E que **todos** los flujos del frontend pasan por PATCH antes del SSE. El CLI usa StoryRunner que tiene su propia transición de estados (no SSE). |

---

## Reversibilidad

- **Slices A, B, C, D** son aditivos. Si algo se rompe, `git revert` deja el sistema estable.
- **Slice E** elimina código defensivo. Si se descubre un caso edge sin red de seguridad, se restaura con un revert puntual.
- Sin cambios de DB ni schema.
- Las nuevas clases (`StreamSession`, `StreamSessionManager`) viven en su propio archivo nuevo — no contaminan archivos existentes.

---

## Open questions

Ninguna pendiente — todas las decisiones cerradas en D1-D7.

---

## Plan técnico

### Hallazgos del research previo al PLAN

| # | Hallazgo | Implicancia |
|---|---|---|
| H1 | Solo existe `tests/integration/test_slice8_e2e_monte.py` (y está roto pre-Spec-218 por falta de `el_monte_prohibido.md`). **No hay infra de tests SSE.** | Slice C debe crear desde cero el setup (httpx.AsyncClient + fastapi lifespan + fixtures asincrónicas). |
| H2 | `StreamEvent` (`src/domain/streaming.py`) ya tiene `event`, `data`, `timestamp` y `to_sse()`. | El replay buffer puede serializar/replay tal cual; no hay que envolver en otra clase. |
| H3 | `StreamEventType` incluye `HEARTBEAT` y `DONE` como enum values claros. | Filtros del replay buffer (skip HEARTBEAT, detectar DONE) son one-liners. |
| H4 | `ObservabilityService` usa `_instance` + `__new__` sin `asyncio.Lock`. Es seguro porque sus mutaciones son sincrónicas. | El `StreamSessionManager` SÍ necesita `asyncio.Lock` por las mutaciones del dict desde corutinas concurrentes (R1 del SPECIFY). |
| H5 | `LLMFactory.get_provider()`, `PromptBuilder()`, `ResponseNormalizer()`, etc. se instancian en `stream_router.stream_generation` líneas 53-65 cada vez que llega una request. | El `producer_factory` que la router pase al manager debe envolver esas instanciaciones — solo se ejecuta la primera vez por sesión. |
| H6 | `StreamSession` debe sobrevivir al productor: si el último consumidor se desconecta antes del DONE, **el productor sigue** (R3) hasta DONE para garantizar persistencia de la generación. | Cleanup condicional: solo eliminar sesión cuando `done_event.is_set() and len(consumers) == 0`. |

### Componentes y dependencias

```
[Slice A] frontend MODO MONITOR (polling)              ── independiente, despliegue inmediato
       │
       ▼
[Slice B] StreamSessionManager + tests unit            ── independiente del frontend
       │  (no toca rutas; nadie lo invoca aún)
       ▼
[Slice C] stream_router cablea al manager + tests int  ── depende de B
       │  (mantiene salvaguarda redundante)
       ▼
[Slice D] frontend MODO MONITOR usa EventSource        ── depende de C (idempotencia real disponible)
       │
       ▼
[Slice E] eliminar salvaguarda redundante              ── depende de C (manager garantiza single-producer)
```

### Orden de implementación

1. **Slice A primero, mergeable solo** — resuelve el bug visible (start-panel) y bloquea la doble conexión SSE accidental. Mientras se implementan B-E el sistema queda saneado por la UI.
2. **Slice B aislado** — manager + tests unit. Sin riesgo: nada lo invoca.
3. **Slice C** — endpoint cablea. Tests integración crean infra SSE desde cero (H1). Verificar que un solo productor corre con multi-cliente.
4. **Slice D** — frontend pasa de polling a EventSource real. Solo posible tras C estable.
5. **Slice E** — eliminar salvaguarda. Solo cuando D verifica que el flujo end-to-end funciona.
6. **Verificación integral** — CA1-CA8 manual + suite completa.

**Mergeo intermedio:** A puede mergearse aislado a `main` (resuelve bug crítico de UX). B+C+D+E pueden agruparse en un PR aparte (cambio estructural).

### Análisis de riesgos (matizado del SPECIFY)

| # | Riesgo | Estado tras research | Mitigación |
|---|---|---|---|
| **R1** | Race condition en `attach` | Confirmado (H4) | `asyncio.Lock` en `StreamSessionManager._lock` protege `_sessions` dict |
| **R2** | Queue lenta llena buffer | Bajo | `asyncio.Queue()` sin `maxsize` (default ilimitada). Monitorear en producción |
| **R3** | Productor sobrevive a desconexión total | Confirmado (H6) | Decisión: NO cancelar — la generación es valiosa, debe completarse y persistir vía `beat_repo.save()` |
| **R4** | Replay buffer crece sin límite | Bajo | `deque(maxlen=50)` por sesión + cleanup tras DONE elimina sesiones inactivas |
| **R5** | Tests integración SSE flaky | **Riesgo elevado** (H1: no existe infra previa para imitar) | Usar `MockLLMAdapter` con yields rápidos; `asyncio.wait_for` con timeout 10s; estructura de fixtures basada en `httpx.AsyncClient` con lifespan manager. Documentar el setup como referencia para tests futuros |
| **R6** | Slice E sin red de seguridad | Bajo | Verificación previa: con manager activo, `streaming_service.stream_story` solo se invoca **una vez** por `story_id` (asegurado por Slice C). El frontend siempre pasa por PATCH `processing` → clear → SSE; el CLI no usa SSE. |
| **R7** | `producer_factory` debe ser invocado dentro del `attach` con el lock liberado para no bloquear otros story_ids | Nuevo (detectado en H5) | El factory crea instancias livianas (`LLMFactory`, `PromptBuilder`, etc.); no es async. Aceptable bajo lock corto. Si se vuelve costoso, refactor a "factory call fuera del lock + atomic check" |

### Verificaciones intermedias

- **Tras Slice A:** smoke 2 pestañas. Pestaña B muestra spinner + beats parciales + log "Esperando…"; DevTools muestra `GET /api/v1/stories/:id` cada 5s; **0 EventSource** en pestaña B; al pasar a `completed`, recarga.
- **Tras Slice B:** `pytest tests/unit/application/services/test_stream_session_manager.py -v` → 7/7 passed.
- **Tras Slice C:** `pytest tests/integration/test_stream_broadcaster.py -v` → 4/4 passed. Smoke 2 pestañas con backend + verificar log backend muestra **un solo** "Iniciando generación".
- **Tras Slice D:** smoke 2 pestañas; pestaña B muestra `beat_done` en vivo simultáneamente con A; DevTools muestra 1 EventSource por pestaña; backend log: 1 pipeline.
- **Tras Slice E:** `pytest tests -v` completo + smoke regen completo.

### Reversibilidad

- **A, B, C, D** son aditivos. `git revert` los recupera completos sin pérdida.
- **E** elimina código defensivo. Si emerge un caso edge, restauración trivial.
- Cero cambios de schema DB; cero migraciones.
- `StreamSession` y `StreamSessionManager` viven en archivo nuevo (`stream_session_manager.py`) — no contaminan código existente.

### Paralelización

| Combinación | Posible? | Justificación |
|---|---|---|
| A + B en paralelo | **Sí** | Frontend (A) y manager nuevo (B) no se tocan. Pueden ir en PRs distintos. |
| A + C en paralelo | No | C requiere B mergeado. |
| C + D en paralelo | No | D depende de la idempotencia que C provee. |
| Implementación serial recomendada | **Sí** | Cada slice introduce verificaciones intermedias que reducen el costo de debug si algo falla. |

### Costo estimado

| Slice | Esfuerzo | Tests |
|---|---|---|
| A | ~30 min | smoke manual |
| B | ~60 min | 7 unit |
| C | ~90 min (incluye crear infra SSE tests) | 4 integración |
| D | ~20 min | smoke manual |
| E | ~10 min | regresión |
| **Total** | **~3.5 hs** | 11 tests nuevos + smoke completo |
