# SPEC-460: Generación asíncrona por jobs + bus de eventos SSE

**Fecha:** 2026-09-22
**Tipo:** SDD (Spec-Driven Development) — arquitectura
**Estado:** DONE (2026-09-22) — S0 a S8 implementados, verificados y desplegados
**Relación:** evoluciona Spec-201/210 (streaming) y Spec-220 (StreamSessionManager). Absorbe el §6 "Feedback de generación" que estaba en Spec-440.

---

## ASSUMPTIONS

1. El Core corre en **un solo proceso** uvicorn (hoy `make api` sin `--workers`). El bus de eventos puede ser en memoria (`asyncio`); multi-worker o Redis quedan fuera de alcance.
2. Se mantienen las 5 restricciones de Spec-201: heartbeat de 15 s vía Queue, idempotencia 409, normalizer antes de emitir por SSE, evento `stream_error` (no `error`) y health check antes de conectar.
3. El browser sigue hablando **solo con Express**; el proxy `/api/*` ya hace passthrough de SSE (Spec-221, `tests/integration/proxy_sse.test.ts`).
4. Consolidar un relato (`generate-narrative`) no usa LLM y es rápido → **sigue síncrono**. Solo se hacen asíncronas las operaciones con LLM.

---

## OBJECTIVE

Pasar de un modelo mixto (la generación arranca con un GET SSE, la regeneración es un POST bloqueante y el estado global se consulta por polling) a un modelo **comando → job → eventos**:

- **Comandos** (`POST`) que arrancan trabajo y devuelven `202 Accepted` con un `job_id` al instante.
- **Jobs** que corren en background, desacoplados de cualquier conexión HTTP.
- **Eventos SSE** que el servidor empuja al cliente: un canal global para todas las páginas y un canal de detalle por job.

**Éxito:** ninguna request HTTP queda colgada esperando al LLM; cualquier página se entera sola (sin polling) de que una generación empezó, avanzó, terminó o falló; y abrir, recargar o volver a una URL nunca dispara una generación.

---

## 0. STACK TECNOLÓGICO

Criterio: usar lo que el proyecto ya tiene instalado. **No se agrega ninguna dependencia nueva.**

| Pieza | Tecnología | Ya está en el proyecto |
|---|---|---|
| Emisión SSE (Core) | `sse-starlette` (`EventSourceResponse`) sobre FastAPI | Sí — `pyproject.toml`, `stream_router.py` |
| Jobs en background | `asyncio.create_task` administrado por `JobManager` (singleton, arranque/parada en el `lifespan` de FastAPI) | Sí — mismo patrón que `StreamSessionManager` |
| Bus de eventos | `asyncio.Queue` por suscriptor (fan-out en memoria) | Sí — ya lo hace `StreamSession.broadcast()` |
| Persistencia de jobs | SQLite vía `aiosqlite`, tabla `generation_job` en `init_db()` | Sí |
| Proxy SSE (Express) | `http-proxy-middleware` en passthrough | Sí — `api_proxy.ts`, cubierto por `proxy_sse.test.ts` |
| Cliente (browser) | `EventSource` nativo + JS vanilla que re-emite `CustomEvent` | Sí — `streaming-room.js` ya usa `EventSource` |
| Refresco parcial de vistas | `htmx.ajax()` (htmx 1.9.10) al recibir `job_done` | Sí — `layout.ejs` |

**Alternativas evaluadas y descartadas:**

- **FastAPI `BackgroundTasks`:** corre después de responder, pero no permite consultar el progreso, deduplicar ni recuperar tras un reinicio.
- **Celery / ARQ / RQ + Redis:** colas distribuidas pensadas para muchos workers. Suman un servicio (Redis) y otro proceso para 1-2 usuarios. Innecesario.
- **Extensión SSE de htmx (`sse-connect` / `sse-swap`):** espera fragmentos HTML por el canal, y nuestros eventos son JSON del Core. Usarla obligaría a Express a traducir JSON → HTML en vivo. Más piezas que el `EventSource` nativo.
- **WebSockets:** bidireccional; acá la comunicación es solo servidor → cliente. SSE es más simple, reconecta solo y pasa por el proxy actual sin cambios.

---

## 1. DIAGNÓSTICO DEL MODELO ACTUAL

| # | Problema | Evidencia |
|---|---|---|
| D1 | **Un GET con efecto secundario:** conectarse a `GET /stories/{id}/stream` **arranca** el pipeline LLM (17 llamadas). La sala lo mitiga porque solo abre el `EventSource` tras el click en "Comenzar", pero la regeneración son 2 requests no atómicas (`PATCH status=processing` + GET SSE), y un reintento o una reconexión automática del `EventSource` pueden volver a iniciar trabajo. | `stream_router.py::stream_generation` → `session_manager.attach(...)`; `streaming-room.js::initiateRegeneration` |
| D2 | **Regenerar acto bloquea la request** durante la llamada LLM (con Ollama pueden ser decenas de segundos). El usuario no ve progreso y el request puede cortarse por timeout. | `beat_router.py::regenerate_beat_voz` (síncrono); `relatos.controller.ts::regenerarActoAction` |
| D3 | **Estado global y modo monitor por polling:** el pie consulta cada 15 s y cada consulta trae **todas** las historias + el último evento. La sala en "modo monitor" (generación iniciada en otra pestaña) también consulta el status en vez de escuchar eventos. | `footer.js`, `stream.controller.ts::getActiveStreamApi`, `streamingRoomPage` (`monitorMode`) |
| D4 | **Estado "activo" inferido de `story.status`:** al arrancar, `recover_processing_stories()` ya pasa `processing → failed` (Spec-214). Pero "hay una generación" se deduce del status de la historia, no de un trabajo real en curso, y no hay historial de ejecuciones. | `main.py::lifespan`, `getActiveStreamApi` |
| D5 | **Sesión huérfana (confirmado en S0):** `detach()` solo borra la sesión si terminó **y** no quedan consumidores. Si el usuario cierra la pestaña a mitad de camino, el productor termina sin nadie conectado y la sesión nunca se borra. Un "Regenerar" posterior se ata a la sesión vieja: recibe el `done` del replay y no genera nada. | `stream_session_manager.py::detach` |
| D6 | **Sin reanudación:** los eventos no llevan `id:`, así que al reconectar se reenvía todo el replay y no hay `Last-Event-ID`. | `StreamEvent.to_sse()` |
| D7 | **"Cancelar" no cancela (confirmado en S0: estados `processing → failed → completed`):** `cancelGeneration()` cierra el `EventSource` y hace `PATCH status=failed`, pero la tarea productora es independiente de la conexión y **sigue llamando al LLM**. Al terminar, `stream_story` pone `status=completed` y pisa el `failed`. | `streaming-room.js::cancelGeneration`; `StreamSession.start_producer` |

---

## 2. MODELO PROPUESTO

```
Browser ──POST /generar──▶ Express ──POST /api/v1/stories/{id}/jobs──▶ Core
                                                      │ 202 {job_id}
                                                      ▼
                                              JobManager.submit()
                                                      │ asyncio.Task (independiente de HTTP)
                                                      ▼
                                              pipeline (Director / Voz)
                                                      │ publish(evento)
                                                      ▼
                                                  EventBus
                                     ┌────────────────┴─────────────────┐
                    GET /api/v1/events (global)          GET /api/v1/jobs/{id}/events (detalle)
                    ciclo de vida + progreso             + prosa por beat + replay
                                     │                                  │
                          Banda de generación,               Sala de streaming
                          botones, galería (todas las páginas)
```

### 2.1 Jobs (backend)

`JobManager` reemplaza a `StreamSessionManager` y conserva lo que ya funciona (productor único por historia, broadcast a N consumidores, replay buffer):

| Tipo (`kind`) | Comando | Antes |
|---|---|---|
| `full_generation` | `POST /api/v1/stories/{id}/jobs` `{kind: "full_generation"}` | lo arrancaba el GET SSE |
| `regenerate_voz` | `POST /api/v1/stories/{id}/jobs` `{kind: "regenerate_voz", beat, narrative_id}` | POST síncrono |

- Respuesta: `202 {job_id, status: "queued"}`.
- **Idempotencia:** si la historia ya tiene un job `queued` o `running` → `409 {job_id}` del job existente, y el frontend redirige a la sala de ese job (Spec-201).
- Estados: `queued → running → done | failed`. `progress = {beat, total_beats, stage}` con `stage ∈ analyst | resolver | mapper | voz | journal | consolidando`.
- **Cancelación real:** `POST /api/v1/jobs/{id}/cancel` → `task.cancel()`. El pipeline se detiene y el job queda `failed` ("cancelada por el usuario") (D7).
- **Regeneración atómica:** `full_generation` con `{regenerate: true}` hace la limpieza de Spec-216/219 dentro del mismo comando; desaparece el `PATCH status=processing` previo (D1).
- **Tabla `generation_job`** (en `init_db()`, sin migraciones): `id, story_id, kind, status, stage, beat, error, narrative_id, created_at, started_at, finished_at`. Sirve para:
  - render server-side del estado inicial (sin esperar al primer evento);
  - **recuperación al arrancar:** se extiende `recover_processing_stories()` para marcar también los jobs `queued`/`running` como `failed` ("interrumpida por reinicio") (D4);
  - historial de generaciones.
- Limpieza de sesiones en memoria por **TTL** (ej. 10 min después de terminar), no por "último consumidor" (D5).

### 2.2 Bus de eventos y canales SSE

`EventBus` en memoria (pub/sub `asyncio`). Todo evento lleva un `id` monotónico por canal (D6).

**Canal global — `GET /api/v1/events`** (una conexión por pestaña, liviano, sin prosa):

| Evento | Payload |
|---|---|
| `job_started` | `{job_id, story_id, title, kind}` |
| `job_progress` | `{job_id, story_id, beat, total_beats, stage}` |
| `job_done` | `{job_id, story_id, title, narrative_id}` |
| `job_failed` | `{job_id, story_id, title, msg}` |
| `snapshot` | al conectar: jobs activos + terminados hace < 60 s |
| `heartbeat` | cada 15 s (también sirve de indicador de conexión con el Core) |

Reemplaza el polling de `footer.js` y de `/system/events`.

**Canal de detalle — `GET /api/v1/jobs/{job_id}/events`**: los eventos actuales de Spec-210 (`status`, `beat_start`, `beat_done`, `heartbeat`, `done`, `stream_error`) con replay y soporte de `Last-Event-ID`. **Solo observa: nunca arranca trabajo** (D1).

**Compatibilidad:** `GET /stories/{id}/stream` se mantiene durante la transición como alias de solo lectura (se ata al job activo o reproduce los beats históricos). Deja de arrancar generaciones.

### 2.3 Cliente (frontend)

- `public/js/event-bus.js` (nuevo, cargado en `layout.ejs`): abre **un único** `EventSource('/api/v1/events')` por pestaña, con guard contra duplicados bajo `hx-boost` (mismo patrón que `window.__footerIntervalId`). Re-emite cada evento como `CustomEvent` en `document` (`forge:job-started`, `forge:job-progress`, …). Los componentes escuchan eventos del DOM y no saben de SSE.
- Consumidores:
  - **Banda de generación** (`partials/generation_banner.ejs`, ver §2.4): título, "Acto N de 5 · etapa", barra de progreso, "Ver progreso" → `/generar/stream/:job_id` (link real, `hx-boost="false"`), estados "lista" y "falló".
  - **Botones de generación** (`data-generation-trigger`, ver §2.4): estado "ocupado" al click; se deshabilitan solos con `job_started` de esa historia y se rehabilitan con `job_done`/`job_failed`.
  - **Regenerar acto** (`relatos.ejs`): POST → 202 → el panel muestra "Regenerando acto N…" → con `job_done` se hace `htmx.ajax` para refrescar solo ese panel. Se elimina la request bloqueante (D2).
  - **Galería / historia:** los badges de estado se actualizan en vivo.
  - **Pie:** queda solo el punto de estado del Core (verde si llegó un heartbeat en los últimos 20 s).
- **Sala de streaming:** consume el canal de detalle del job. El botón "Comenzar" pasa a ser un `<form method="POST">` que crea el job y redirige a la sala.
- **Una sola conexión SSE por pestaña:** en la sala de streaming se abre el canal de detalle y **no** el global (la sala ya muestra todo lo de su job). En el resto de las páginas, solo el global. Así se evita el límite de conexiones simultáneas del navegador (ver Decisiones) sin mecanismos extra.

### 2.4 Diseño de UI

**Problemas reportados que esto resuelve:**

- "Generar historia" (`wizard-confirm.ejs`) sigue habilitado después del click → el usuario vuelve a clickear.
- "GENERANDO" es texto de 10 px en el pie, gris sobre gris: casi no se ve.
- `#footer-active-content` no arranca con `hidden` → "GENERANDO: · VER PROGRESO" aparece vacío aunque no haya generación.
- "Ver progreso" nace con `href="#"` y solo se completa si el polling encuentra una historia en `processing` → casi siempre no hace nada.

**Botones de generación** (`public/js/generation-guard.js`; aplica a Generar, Regenerar, Comenzar y Regenerar acto):

- Al click: todos los triggers de la página se deshabilitan (`disabled`, `aria-busy="true"`), el ícono cambia a spinner y el texto a `data-busy-label` ("Iniciando generación…") en < 100 ms.
- En `pageshow` con `event.persisted` (volver atrás con bfcache) se restaura el estado original.
- Estado inicial server-side: si la historia tiene un job activo (`generation_job`), se renderiza deshabilitado como "Generando…" con link "Ver progreso".

**Banda de generación** (arriba del contenido, a todo el ancho del área principal; reemplaza el bloque del pie):

| Estado | Aspecto |
|---|---|
| Sin jobs | Banda oculta (arranca `hidden` en el HTML). |
| `running` | Fondo `forge-accent` al 15 % + borde inferior accent · punto pulsante · **«Título»** en serif · "Acto 3 de 5 · Narrando" · barra de progreso fina · botón "Ver progreso". |
| `done` | Éxito: "«Título» está lista" + "Leer relato". Se puede cerrar; se oculta sola a los 15 s. |
| `failed` | Rojo: "Falló la generación de «Título»" + "Ver detalle". Queda hasta que se cierra. |

- "Ver progreso" es un `<a>` real a la sala del job y **solo existe cuando hay un `job_id`**; nunca `href="#"`. Lleva `hx-boost="false"`.
- No se muestra en la sala de ese mismo job.
- El ítem "Nuevo relato" del sidebar suma un punto pulsante mientras hay jobs activos.
- `role="status"` + `aria-live="polite"`; respeta `prefers-reduced-motion`.
- Varios jobs a la vez: la banda muestra el más reciente + "y N más".

### 2.5 Guardar y generar, desacoplados (pedido 2026-09-22)

Hoy el paso final del wizard mezcla dos cosas: al avanzar el último paso **guarda en silencio** (`wizard.controller.ts::submitStep`: "Si la persistencia falla, igual avanzamos a confirmar") y la pantalla de confirmación ofrece "Generar historia". Si el guardado falló, el usuario no se entera y la generación falla después.

Nuevo flujo:

1. **El wizard termina en "Guardar historia".** `wizard-confirm.ejs` reemplaza los dos botones "Generar historia" por un único **"Guardar historia"** (POST si es nueva, PATCH si ya existe `wizard_story_id`).
   - Éxito → redirige a la **galería** con aviso "«Título» guardada" y la tarjeta de esa historia resaltada.
   - Error → se queda en la confirmación mostrando el error del Core (validación 422, Core caído, etc.). **Nunca se traga el error.**
   - `submitStep` deja de guardar en silencio al pasar el último paso: el guardado ocurre solo con el botón explícito.
2. **La generación se inicia solo desde el listado** (galería) y desde la ficha de la historia.
   - Tarjeta en `draft`/`pending`/`failed` → botón **"Generar"** (o "Reintentar"); en `completed` → "Regenerar" (con la confirmación no destructiva de Spec-219).
   - El botón crea el job (`POST /jobs`) y lleva a la sala; mientras el job corre, la tarjeta muestra "Generando · Acto N/5" en vivo (canal global) con link "Ver avance", y sus botones quedan deshabilitados.
   - Se elimina `POST /generar/submit` (crear + generar en un paso).

---

## 3. CRITERIOS DE ACEPTACIÓN

- Recargar `/generar/stream/:id` 5 veces seguidas → sigue habiendo **1 solo** job (verificable en `generation_job`) y 17 llamadas LLM.
- `POST /jobs` con un job activo → 409 con el `job_id` existente; el frontend redirige a la sala.
- Regenerar un acto → el request HTTP vuelve en < 500 ms; el panel se actualiza solo al terminar.
- Con una generación en curso, abrir cualquier página → la banda aparece en < 1 s (evento `snapshot`), sin polling (verificable en la pestaña Network: 1 `EventSource` y ninguna consulta periódica).
- Cerrar la pestaña a mitad de camino → el job termina igual; un "Regenerar" posterior crea un job **nuevo** (D5).
- Matar el Core a mitad de un job y levantarlo → el job queda `failed` ("interrumpida") y la historia no queda en `processing`.
- Click en "Generar historia" → botón deshabilitado con spinner en < 100 ms; un doble click genera 1 solo POST.
- Sin jobs: no aparece ningún "GENERANDO", ni siquiera al cargar la página.
- "Ver progreso" siempre navega a la sala del job en curso.
- Terminar el wizard → "Guardar historia" → vuelve a la galería con la historia guardada; si el Core devuelve error, se ve en la confirmación.
- Desde la galería, "Generar" en una historia guardada → sala con el job en curso; la tarjeta muestra el avance en vivo.
- Cortar la red 10 s → el `EventSource` reconecta con `Last-Event-ID` y no duplica beats en la sala.

---

## 4. PROJECT STRUCTURE (preliminar)

```
src/domain/jobs.py                                  # Job, JobKind, JobStatus, JobProgress
src/domain/streaming.py                             # StreamEvent con id; eventos job_*
src/application/services/job_manager.py             # reemplaza stream_session_manager.py
src/application/services/event_bus.py               # pub/sub en memoria
src/application/services/streaming_service.py       # publica progress/stage en el bus
src/application/use_cases/regenerate_beat_voz.py    # corre como job
src/infrastructure/database/connection.py           # tabla generation_job
src/infrastructure/database/repositories/job_repository.py
src/presentation/routers/job_router.py              # POST /stories/{id}/jobs, GET /jobs/{id}/events
src/presentation/routers/events_router.py           # GET /events
src/presentation/routers/stream_router.py           # /stream pasa a solo lectura
src/main.py                                         # lifespan: recuperar jobs huérfanos
frontend/public/js/event-bus.js                     # NUEVO
frontend/public/js/generation-guard.js              # NUEVO
frontend/public/js/footer.js                        # se reduce al punto de estado del Core
frontend/public/js/streaming-room.js                # canal de detalle por job
frontend/src/views/partials/generation_banner.ejs   # NUEVO
frontend/src/views/{wizard-confirm,historia,relatos}.ejs
frontend/src/controllers/{stream,relatos,historia}.controller.ts
```

---

## 5. TESTING STRATEGY

- **Backend unit:** `JobManager` (idempotencia, 409, TTL, recuperación de huérfanos), `EventBus` (fan-out, ids monotónicos, replay desde `Last-Event-ID`), `generation_job` repo.
- **Backend integración:** `POST /jobs` + `GET /jobs/{id}/events` con `MockLLMAdapter`; el GET nunca crea jobs.
- **Frontend integración:** passthrough SSE de `/api/v1/events` (extender `proxy_sse.test.ts`).
- **E2E Playwright:** banda en vivo con backend mock; doble click → 1 POST; regenerar acto sin request bloqueante; reconexión.
- Lint y tests los corro yo en cada checkpoint (output filtrado) y reporto el resultado.

---

## PLAN

### Estrategia

**Stack:** todas las etapas usan solo lo definido en §0 (nada nuevo). Cada slice indica abajo qué piezas usa.

**Risk-first + vertical.** Lo más riesgoso es el ciclo de vida de las tareas `asyncio` (heartbeat, cancelación, limpieza), así que va primero y aislado. Después se conecta capa por capa, con una regla: **al cerrar cada slice la app funciona de punta a punta**. Por eso el `GET /stream` legado sigue arrancando generaciones (ahora a través de `JobManager`) hasta que la sala migra en S4, y recién ahí pasa a solo lectura.

Al cerrar cada slice corro lint y tests, te reporto el resultado y, con tu OK, se commitea.

### Mapa de slices

```
S0 Confirmar D5/D7 ──▶ S1 Job + tabla ──▶ S2 JobManager + EventBus ──▶ S3 API de jobs
                                                                          │
                              ┌───────────────────────────────────────────┤
                              ▼                                           ▼
                        S4 Sala sobre jobs                         S5 Canal global + banda
                              │                                           │
                              └──────────────┬────────────────────────────┘
                                             ▼
                              S6 Botones ──▶ S7 Regenerar acto como job ──▶ S8 Limpieza
```

### S0 — Confirmar hallazgos D5 y D7 (tests en rojo)

- **Stack:** `pytest` + `pytest-asyncio` + `MockLLMAdapter` (ya en el proyecto).

- **Qué:** tests de `pytest` que reproducen (a) la sesión huérfana que bloquea un "Regenerar" posterior y (b) el cancelar que no detiene el productor, con `MockLLMAdapter`.
- **Por qué primero:** si no se reproducen, se ajusta el diagnóstico antes de construir encima. Son los tests de regresión que S2 tiene que poner en verde.
- **Archivos:** `tests/unit/application/test_stream_session_manager.py` (nuevo).
- **Estado del sistema:** sin cambios de código productivo.

### S1 — Dominio y persistencia de jobs

- **Stack:** Pydantic/dataclasses de dominio, SQLite vía `aiosqlite`, `init_db()`, `lifespan` de FastAPI.

- **Qué:** `Job`, `JobKind`, `JobStatus`, `JobProgress` en `src/domain/jobs.py`; tabla `generation_job` en `init_db()`; `SQLJobRepository` (`create`, `update_progress`, `finish`, `get`, `get_active_for_story`, `list_recent`); extender `recover_processing_stories()` para marcar jobs `queued`/`running` como `failed`.
- **Archivos:** `src/domain/jobs.py`, `connection.py`, `repositories/job_repository.py`, `story_repository.py`, `main.py`.
- **Verificación:** tests unitarios del repo + recuperación. Recrear `stories.db`.
- **Estado del sistema:** igual que hoy (la tabla existe, nadie la usa todavía).

### S2 — `JobManager` + `EventBus` (núcleo, sin HTTP)

- **Stack:** `asyncio` puro (`create_task`, `Queue`, `Event`, `Lock`). Sin librerías de colas.

- **Qué:**
  - `EventBus`: pub/sub en memoria; `subscribe()` devuelve una `Queue`; ids monotónicos; replay desde `Last-Event-ID`.
  - `JobManager.submit(story, kind, **params)`: crea el job en DB, lanza la `Task`, traduce los `StreamEvent` de `stream_story` a (a) canal de detalle del job y (b) eventos `job_*` del canal global; actualiza `stage`/`beat` en DB.
  - Idempotencia (1 job activo por historia), `cancel(job_id)`, limpieza por TTL.
  - `StreamEvent` suma `id` y los tipos `job_started|job_progress|job_done|job_failed|snapshot`. `stream_story` emite `stage` en sus eventos `status` (hoy manda `step` con `analyst`/`mapper`; se completa con `voz`/`journal`/`consolidando`).
- **Restricciones de Spec-201:** el heartbeat sigue saliendo de `stream_story` (Queue compartida); el normalizer no cambia de lugar; `stream_error` se mantiene.
- **Archivos:** `src/application/services/{event_bus,job_manager}.py`, `src/domain/streaming.py`, `streaming_service.py`.
- **Verificación:** tests unitarios con `MockLLMAdapter`: fan-out a 2 suscriptores, replay por id, 409 lógico, cancelación real, TTL. **Los tests de S0 pasan a verde** contra `JobManager`.
- **Estado del sistema:** igual que hoy (el núcleo existe, los routers siguen con `StreamSessionManager`).

### S3 — API de jobs + `/stream` legado sobre `JobManager`

- **Stack:** routers FastAPI + `sse-starlette` (`EventSourceResponse`, campo `id` para `Last-Event-ID`); tests con `httpx.AsyncClient`.

- **Qué:**
  - `POST /api/v1/stories/{id}/jobs` → 202 / 409; `{regenerate: true}` hace la limpieza de Spec-216 dentro del comando.
  - `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs/{id}/events` (SSE, replay + `Last-Event-ID`), `POST /api/v1/jobs/{id}/cancel`.
  - `GET /stories/{id}/stream` pasa a usar `JobManager` por dentro (si no hay job activo, lo crea: **comportamiento legado**). La sala actual sigue funcionando sin tocar el frontend.
- **Archivos:** `src/presentation/routers/job_router.py`, `stream_router.py`, `main.py`, schemas.
- **Verificación:** tests de integración con `httpx.AsyncClient` + mock LLM; el flujo web actual, probado a mano, sigue igual.
- **Estado del sistema:** web sin cambios visibles; D5 y D7 resueltos del lado del backend.

### S4 — Sala de streaming sobre jobs

- **Stack:** `EventSource` nativo + `fetch` en JS vanilla (`streaming-room.js`), EJS, controller Express/TypeScript; E2E con Playwright.

- **Qué:**
  - "Comenzar" / "Regenerar": `POST /api/v1/stories/{id}/jobs` → con el `job_id`, abrir `EventSource('/api/v1/jobs/{job_id}/events')`. Se elimina el `PATCH status=processing` previo.
  - Modo monitor: si hay un job activo, se conecta a su canal de detalle (sin polling de status).
  - "Cancelar" → `POST /jobs/{id}/cancel`.
  - 409 → la sala se ata al job existente.
  - `GET /stories/{id}/stream` pasa a **solo lectura** (alias: se ata al job activo o reproduce el histórico; nunca crea jobs). **Cierra D1.**
- **Archivos:** `streaming-room.js`, `streaming-room.ejs`, `stream.controller.ts` (`streamingRoomPage` recibe el job activo), `stream_router.py`.
- **Verificación:** Playwright: generar con backend mock, recargar la sala a mitad de camino (1 solo job), cancelar (el job queda `failed`, no llegan más `beat_done`).
- **Estado del sistema:** generación completa sobre jobs; el pie todavía hace polling.

### S5 — Canal global, banda de generación y pie

- **Stack:** FastAPI + `sse-starlette` (canal global); Express con `http-proxy-middleware` en passthrough; `EventSource` nativo + `CustomEvent` en JS vanilla; partial EJS + clases Tailwind del tema actual; tests con Vitest (proxy) y Playwright.

- **Qué:**
  - `GET /api/v1/events` (snapshot al conectar + `job_*` + heartbeat).
  - `public/js/event-bus.js`: un `EventSource` por pestaña (el global, **salvo en la sala**), re-emite `CustomEvent`s, con guard contra `hx-boost`.
  - `partials/generation_banner.ejs` + su JS (estados de §2.4); punto pulsante en el sidebar.
  - El pie queda solo con el indicador del Core (alimentado por heartbeat); se elimina `/internal/streaming/active` y su polling.
- **Archivos:** `events_router.py`, `event-bus.js`, `generation_banner.ejs`, `layout.ejs`, `sidebar.ejs`, `footer.ejs`, `footer.js`, `routes/index.ts`, `stream.controller.ts`.
- **Verificación:** Playwright: la banda aparece al iniciar un job desde otra página, muestra acto N/5, "Ver progreso" navega, pasa a "lista". En Network: una sola conexión SSE y ninguna consulta periódica. Extender `proxy_sse.test.ts` para `/api/v1/events`.
- **Estado del sistema:** D3 resuelto; problemas de UI reportados resueltos (salvo los botones).

### S6 — Botones en estado ocupado + guardar/generar desacoplados

- **Stack:** JS vanilla (`generation-guard.js`), atributos `data-*` en EJS, controllers Express; Playwright.

- **Qué:** `generation-guard.js` + `data-generation-trigger` / `data-busy-label` en `wizard-confirm.ejs`, `historia.ejs` y `streaming-room.ejs`; estado inicial server-side desde el job activo; escucha `forge:job-*` para habilitarse y deshabilitarse; restauración en `pageshow`. Los POST de Express (`submitGeneration`, `generarDesdeHistoria`) crean el job y redirigen a la sala; 409 → redirige a la sala del job existente.
- **Verificación:** Playwright: doble click → 1 POST; volver atrás no deja el botón trabado.

### S7 — Regenerar acto como job (`regenerate_voz`)

- **Stack:** `JobManager` (S2) + `htmx.ajax()` de htmx 1.9.10 para refrescar el panel; controller Express.

- **Qué:** `JobManager` soporta `kind=regenerate_voz` envolviendo `RegenerateBeatVozUseCase`; `relatos.controller.ts` hace POST → 202 y devuelve el panel en estado "Regenerando acto N…"; con `forge:job-done` de ese job, `htmx.ajax` refresca solo ese panel. Se retira `POST /beats/{n}/regenerate-voz` síncrono. **Cierra D2.**
- **Verificación:** test de integración del job; Playwright: el request vuelve en < 500 ms y el panel se actualiza solo.

### S8 — Limpieza y documentación

- **Stack:** sin tecnología nueva; `ruff`, `pytest`, Vitest y Playwright para la verificación final.

- **Qué:** eliminar `StreamSessionManager` y sus tests obsoletos; decidir si `/system/events` queda (lo usa `/debug`); actualizar `CLAUDE.md` (secciones *Web & Streaming* y *Data Flow*) y marcar Spec-460 como DONE; actualizar referencias en Spec-210/220.
- **Verificación:** `make lint`, `make test`, suite Playwright completa.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Tareas `asyncio` que quedan vivas o se cancelan de más al cerrar conexiones | S2 aislado y testeado sin HTTP; la tarea del job no depende de ningún consumidor. |
| Reload de uvicorn (`--reload`) en dev mata jobs a mitad de camino | Esperado: la recuperación al arrancar los marca `failed`. Documentarlo. |
| El proxy Express bufferiza el SSE global | Ya hay passthrough probado; S5 extiende `proxy_sse.test.ts`. |
| `hx-boost` duplica el `EventSource` al navegar | Guard en `window` (mismo patrón que el fix de `footer.js`) + test E2E que cuenta conexiones. |
| Romper Spec-430 (regenerar acto) | S7 va al final, con la sala y el bus ya estables. |

## TASKS

Formato: cada tarea tiene **Acceptance** (qué tiene que ser cierto), **Verify** (cómo se comprueba) y **Files**. Al final de cada slice hay un **Checkpoint**: corro lint y tests, te reporto el resultado y, con tu OK, se commitea.

### S0 — Confirmar D5 y D7

- [x] **T0.1:** Test que reproduce D5 (sesión huérfana).
  - Acceptance: el productor termina con 0 consumidores → un `attach()` posterior para el mismo `story_id` **debería** arrancar un productor nuevo. El test falla hoy (queda atado a la sesión vieja).
  - Verify: `uv run pytest tests/unit/application/services/test_stream_session_manager.py -k huerfana -v` → FAIL esperado.
  - Files: `tests/unit/application/services/test_stream_session_manager.py`
- [x] **T0.2:** Test que reproduce D7 (cancelar no cancela).
  - Acceptance: con un productor lento, desconectar al único consumidor + marcar la historia `failed` → el productor **no debería** seguir emitiendo ni pasar la historia a `completed`. El test falla hoy.
  - Verify: `... -k cancelar -v` → FAIL esperado.
  - Files: ídem T0.1
- [x] **Checkpoint S0:** si alguno **no** falla, se corrige el diagnóstico (D5/D7) antes de seguir. Los tests se marcan `xfail(strict=True)` hasta S2.

### S1 — Dominio y persistencia de jobs

- [x] **T1.1:** Modelos de dominio del job.
  - Acceptance: `JobKind` (`full_generation`, `regenerate_voz`), `JobStatus` (`queued`, `running`, `done`, `failed`), `JobStage` (`analyst`, `resolver`, `mapper`, `voz`, `journal`, `consolidando`), `Job` con `id, story_id, kind, status, stage, beat, total_beats, params, error, narrative_id, created_at, started_at, finished_at` y `is_active`.
  - Verify: `uv run pytest tests/unit/domain/test_jobs.py -v`
  - Files: `src/domain/jobs.py`, `tests/unit/domain/test_jobs.py`
- [x] **T1.2:** Tabla `generation_job` en `init_db()`.
  - Acceptance: columnas de T1.1 (`params` como JSON); FK `story_id → story(id) ON DELETE CASCADE`; índice `(story_id, status)`; **índice único parcial** `(story_id) WHERE status IN (queued, running)`: un solo job activo por historia garantizado por la DB.
  - Verify: `uv run pytest tests/unit/infrastructure/test_db_connection.py -v`. Tabla nueva = cambio aditivo: `CREATE TABLE IF NOT EXISTS` la crea al arrancar, **no hace falta recrear la DB** (verificado en dev: historias intactas).
  - Files: `src/infrastructure/database/connection.py`, `tests/unit/infrastructure/test_db_connection.py`
- [x] **T1.3:** `SQLJobRepository`.
  - Acceptance: `create`, `mark_running`, `update_progress(stage, beat)`, `finish(status, error, narrative_id)`, `get`, `get_active_for_story`, `list_active`, `list_recent(since)`.
  - Verify: `uv run pytest tests/unit/infrastructure/test_job_repository.py -v`
  - Files: `src/infrastructure/database/repositories/job_repository.py` (+ export en `__init__.py`), `tests/unit/infrastructure/test_job_repository.py`
- [x] **T1.4:** Recuperación al arrancar.
  - Acceptance: `SQLJobRepository.recover_interrupted()` pasa los jobs `queued`/`running` a `failed` con `error="interrumpida por reinicio"`; `main.py::lifespan` lo llama junto a `recover_processing_stories()`.
  - Verify: test del repo con un job `running` precargado.
  - Files: `story_repository.py` (o `job_repository.py` + llamada en `main.py::lifespan`)
- [x] **Checkpoint S1:** `make lint && make test`. La app funciona igual que hoy.

### S2 — `JobManager` + `EventBus` (sin HTTP)

- [x] **T2.1:** `StreamEvent` con `id` y eventos de ciclo de vida.
  - Acceptance: campo opcional `id: int | None`; `to_sse()` lo incluye si existe; nuevos tipos `job_started`, `job_progress`, `job_done`, `job_failed`, `snapshot`. Los tipos existentes no cambian (`stream_error` se mantiene).
  - Verify: `uv run pytest tests/unit/domain -k streaming -v`
  - Files: `src/domain/streaming.py`
- [x] **T2.2:** `stream_story` informa la etapa.
  - Acceptance: los eventos `status` llevan `stage` ∈ `JobStage` (hoy `step` solo usa `analyst`/`mapper`) y `beat`; se agrega `consolidando` antes de consolidar. Heartbeat intacto (Spec-201).
  - Implementado: `DirectorUseCase.execute_full(on_stage=...)` — callback estructurado `(JobStage, beat)` junto al `on_step_start` de texto (CLI, sin cambios). `prepare_story` llama cada callback dos veces (inicio/fin): `resolver` se emite en la primera. `stream_story` lo traduce con `stage_event()` (`msg`, `step` legado, `stage`, `beat`, `total_beats`).
  - Verify: `uv run pytest tests/unit/application/services/test_streaming_service.py -v`
  - Files: `src/application/services/streaming_service.py`
- [x] **T2.3:** `EventBus`.
  - Acceptance: canales por nombre (`global`, `job:<id>`); `publish()` asigna id monotónico por canal y guarda los últimos N (no heartbeats); `subscribe(channel, last_event_id=None)` devuelve `(queue, replay)` con solo los eventos posteriores a `last_event_id`; `unsubscribe()`; `drop(channel)`.
  - Verify: `uv run pytest tests/unit/application/services/test_event_bus.py -v` (fan-out a 2 suscriptores, replay por id, heartbeats fuera del buffer).
  - Files: `src/application/services/event_bus.py` + test
- [x] **T2.4:** `JobManager.submit()` para `full_generation`.
  - Acceptance: crea el job en DB (`queued`); si ya hay uno activo para la historia → `JobAlreadyActive(job_id)`; lanza la `Task` independiente de consumidores; publica en `job:<id>` todos los eventos de `stream_story` y en `global` `job_started` / `job_progress` (con cada cambio de `stage`/`beat`) / `job_done` / `job_failed`; persiste el progreso en DB.
  - Verify: test con `MockLLMAdapter`: secuencia completa de eventos en ambos canales; segundo `submit` → excepción con el mismo `job_id`.
  - Files: `src/application/services/job_manager.py`, `tests/unit/application/services/test_job_manager.py`
- [x] **T2.5:** Regeneración atómica.
  - Acceptance: `submit(..., regenerate=True)` ejecuta la limpieza de Spec-216/219 (la misma que hoy dispara `PATCH status=processing`) dentro del job, antes del pipeline.
  - Verify: test: beats/journal/anchors previos se borran solo cuando arranca el job.
  - Files: `job_manager.py` (reusa la lógica de `update_story_status`)
- [x] **T2.6:** Cancelación real.
  - Acceptance: `cancel(job_id)` → `task.cancel()`; el job queda `failed` con `error="cancelada por el usuario"`; la historia queda `failed` y **no** pasa a `completed`; se publica `job_failed`.
  - Verify: test con productor lento; **T0.2 portado a `JobManager` pasa a verde**.
  - Files: `job_manager.py` + test
- [x] **T2.7:** Limpieza por TTL y `snapshot`.
  - Acceptance: el canal `job:<id>` se descarta N minutos después de terminar, haya o no consumidores; un `submit` nuevo tras terminar crea job nuevo; `snapshot()` devuelve jobs activos + terminados hace < 60 s.
  - Verify: test con TTL corto; **T0.1 portado pasa a verde**.
  - Files: `job_manager.py` + test
- [x] **T2.8:** Singleton y ciclo de vida.
  - Acceptance: instancia única del módulo; en el cierre del `lifespan` se cancelan los jobs vivos (quedan `failed` con "interrumpida por reinicio").
  - Implementado en `src/presentation/runtime.py` (composition root: la capa de aplicación no importa repos de infraestructura), no en `job_manager.py`.
  - Files: `src/presentation/runtime.py`, `src/main.py`
- [x] **Checkpoint S2:** `make lint && make test`. La app funciona igual (los routers todavía no usan el `JobManager`).

### S3 — API de jobs + `/stream` legado sobre `JobManager`

- [x] **T3.1:** `POST /api/v1/stories/{id}/jobs`.
  - Acceptance: body `{kind: "full_generation"}` → `202 {job_id, status}`; historia inexistente → 404; job activo → `409 {detail, job_id}`.
  - Implementado sin flag `regenerate`: `full_generation` **siempre** limpia los artefactos previos dentro del job (hoy el frontend hace `PATCH status=processing` antes de toda generación, también en borradores). Verificado que no se pierde el texto de los actos: el director corta `story.sinopsis` por párrafos, no lee `macro_beat.synopsis_beat`. La confirmación de Spec-219 queda en la UI. `regenerate_voz` → 422 hasta S7.
  - Verify: `uv run pytest tests/unit/presentation/routers/test_job_router.py -v`
  - Files: `src/presentation/routers/job_router.py`, `src/presentation/schemas/{request,response}.py`, `src/presentation/routers/__init__.py`, `src/main.py`
- [x] **T3.2:** `GET /api/v1/jobs/{id}` y `POST /api/v1/jobs/{id}/cancel`.
  - Acceptance: el GET devuelve el estado del job desde DB; el cancel sobre un job activo → **200 con el job ya `failed`** (la cancelación es síncrona: espera a que el pipeline se detenga), sobre uno terminado → 409.
  - Verify: tests del router.
  - Files: `job_router.py`
- [x] **T3.3:** `GET /api/v1/jobs/{id}/events` (SSE de detalle).
  - Acceptance: `EventSourceResponse` sobre `EventBus.subscribe("job:<id>", Last-Event-ID)`; cada evento lleva `id:`; cierra tras `done`/`stream_error`; job terminado y canal ya descartado → reproduce los beats desde DB y cierra; **nunca crea jobs**.
  - Verify: test con `httpx.AsyncClient` + mock LLM: reconectar con `Last-Event-ID` no repite eventos.
  - Files: `job_router.py`
- [x] **T3.4:** `GET /stories/{id}/stream` legado sobre `JobManager`.
  - Acceptance: mismo contrato de eventos que hoy; si no hay job activo y la historia no está `completed`/`failed`, crea uno vía `JobManager` (comportamiento legado temporal); si hay uno, se ata a su canal. `StreamSessionManager` deja de usarse en el router.
  - Verify: la sala actual genera una historia completa sin cambios en el frontend (prueba manual con `--mock`); los tests del router existentes pasan.
  - Files: `src/presentation/routers/stream_router.py`
- [x] **Checkpoint S3:** `make lint && make test` + prueba manual en la web: generar, regenerar y cancelar funcionan como antes.
  - Verificado con el frontend **sin cambios** (API de prueba con LLM mock lento + copia de la DB dev, Playwright): regenerar desde la ficha → confirmación Spec-219 → 5 actos + consolidación → `completed`; recargar la sala a mitad de camino no duplica jobs.
  - Visto para S4: la sala loguea "Narrando Beat N" **después** de las etapas del beat, porque `stream_story` emite `beat_start` cuando el beat ya terminó (preexistente; ahora se nota por los eventos de etapa).
  - "Cancelar" desde la sala sigue sin detener el job hasta S4 (el frontend todavía hace `PATCH status=failed`, no `POST /jobs/{id}/cancel`).

### S4 — Sala de streaming sobre jobs

- [x] **T4.1:** `streamingRoomPage` conoce el job activo.
  - Acceptance: el controller consulta el job activo de la historia y lo pasa a la vista (`activeJobId`); desaparece el cálculo de `monitorMode` basado en `story.status`.
  - Files: `frontend/src/controllers/stream.controller.ts`, `frontend/src/services/core_api.service.ts`
- [x] **T4.2:** "Comenzar" y "Regenerar" crean el job.
  - Acceptance: `initiateGeneration()` / `initiateRegeneration()` hacen `POST /api/v1/stories/{id}/jobs` (`regenerate: true` en el segundo) y abren `EventSource('/api/v1/jobs/{job_id}/events')`; ante 409 se atan al `job_id` devuelto; se elimina el `PATCH status=processing`.
  - Files: `frontend/public/js/streaming-room.js`, `frontend/src/views/streaming-room.ejs`
- [x] **T4.3:** Modo monitor sin polling.
  - Acceptance: si hay `activeJobId`, la sala se conecta directo a su canal de detalle y recibe el replay; se elimina el polling de status.
  - Files: `streaming-room.js`, `streaming-room.ejs`
- [x] **T4.4:** "Cancelar" cancela.
  - Acceptance: `cancelGeneration()` → `POST /api/v1/jobs/{id}/cancel`; se elimina el `PATCH status=failed`.
  - Files: `streaming-room.js`
- [x] **T4.5:** `/stories/{id}/stream` a solo lectura.
  - Acceptance: el GET nunca crea jobs; con job activo se ata a él; sin job, reproduce el histórico.
  - Verify: test: GET sobre una historia `pending` sin job → no se crea ninguna fila en `generation_job`.
  - Files: `src/presentation/routers/stream_router.py`
- [x] **T4.6:** E2E de la sala.
  - Acceptance: con backend mock: generar → 5 `beat_done` → `done`; recargar a mitad de camino → sigue el mismo job; cancelar → el badge pasa a cancelada y no llegan más beats.
  - Verify: `cd frontend && npx playwright test streaming-room.spec.ts`
  - Files: `frontend/tests/e2e/streaming-room.spec.ts`, `frontend/tests/helpers/mock_backend.ts` (helper de SSE)
- [x] **Checkpoint S4:** `make test`, `cd frontend && npm test && npx playwright test`. **D1 y D7 cerrados en uso real.**
  - Implementado / desvíos:
    - Nuevo `GET /stories/{id}/jobs/active` (el controller lo usa para `activeJobId`).
    - **Modo monitor eliminado**: con un job activo la sala usa el modo principal y se ata sola (tiene "Cancelar"). Se borró `streaming-monitor.js`. Corrección al diagnóstico D3: el monitor no hacía polling, usaba EventSource contra `/stream`.
    - "Cancelar" solo existía en el panel de error: se agregó un botón visible mientras la generación corre.
    - Adelantado de T6.4: `generarDesdeHistoria` y `submitGeneration(action=generate)` lanzan el job en el servidor (`startGeneration`) y redirigen a la sala; se eliminó el `PATCH status=processing`. Esto arregla el wizard: "Generar historia" creaba un borrador y la sala lo mostraba en modo lectura, **sin forma de iniciar la generación**.
    - `beat_start` sale al empezar el mapeo del acto (antes salía cuando el acto ya había terminado); respaldo al final del beat si el director no informa etapas.
    - `/stories/{id}/stream` sin job y sin completar → `stream_error` ("No hay una generación en curso").
    - **Arnés E2E**: `playwright.config.ts` levanta su propio Core (`tests/e2e_support/run_api_mock.py`: DB descartable sembrada desde `data/dev/stories.db`, LLM mock con demora) y frontend en :8021/:3021. Antes apuntaba a :3010 con `reuseExistingServer`, que en esta máquina es un `browser-sync` de otro proyecto. Con `BASE_URL` se usa un frontend existente.
    - `relatos.spec.ts`: el test de cambio de pestaña se salteaba siempre (la DB dev tiene 1 relato); con el arnés crea el 2º relato antes y corre.

### S5 — Canal global, banda y pie

- [x] **T5.1:** `GET /api/v1/events`.
  - Acceptance: al conectar emite `snapshot`; después, `job_*` en vivo y `heartbeat` cada 15 s; soporta `Last-Event-ID`.
  - Verify: `uv run pytest tests/unit/presentation/routers/test_events_router.py -v`
  - Files: `src/presentation/routers/events_router.py`, `__init__.py`, `main.py`
- [x] **T5.2:** Passthrough del canal global en Express.
  - Acceptance: `/api/v1/events` llega sin bufferizar (el primer evento en < 1 s).
  - Verify: `cd frontend && npx vitest run tests/integration/proxy_sse.test.ts`
  - Files: `frontend/tests/integration/proxy_sse.test.ts` (y `api_proxy.ts` solo si hiciera falta)
- [x] **T5.3:** `event-bus.js`.
  - Acceptance: abre un único `EventSource('/api/v1/events')` por pestaña (guard en `window` contra `hx-boost`); **no** lo abre en la sala (`data-page="streaming-room"`); re-emite `forge:job-started|progress|done|failed|snapshot` y `forge:core-alive`; mantiene en `window.__forgeJobs` el estado de los jobs activos.
  - Files: `frontend/public/js/event-bus.js`, `frontend/src/views/partials/layout.ejs`
- [x] **T5.4:** Banda de generación.
  - Acceptance: estados de §2.4 (oculta / `running` / `done` / `failed`); "Ver progreso" es un `<a>` real con `hx-boost="false"` que solo existe con `job_id`; `role="status"` + `aria-live="polite"`; `prefers-reduced-motion`; "y N más" si hay varios jobs.
  - Files: `frontend/src/views/partials/generation_banner.ejs`, `frontend/public/js/generation-banner.js`, `layout.ejs`, `frontend/src/styles/globals.css`
- [x] **T5.5:** Punto pulsante en el sidebar.
  - Acceptance: el ítem "Nuevo relato" muestra el punto mientras hay jobs activos.
  - Files: `frontend/src/views/partials/sidebar.ejs`, `generation-banner.js`
- [x] **T5.6:** Pie simplificado.
  - Acceptance: se elimina el bloque "Generando"; el indicador del Core se pone verde con `forge:core-alive` (heartbeat en los últimos 20 s) y rojo si no llega; se eliminan el polling de `footer.js`, la ruta `/internal/streaming/active` y `getActiveStreamApi`.
  - Files: `footer.ejs`, `footer.js`, `frontend/src/routes/index.ts`, `stream.controller.ts`
- [x] **T5.7:** E2E de la banda.
  - Acceptance: con un job iniciado desde otra página, la banda aparece en < 1 s con título y acto N/5; "Ver progreso" navega a la sala; al terminar muestra "está lista"; en Network hay 1 `EventSource` y ninguna consulta periódica; sin jobs no aparece "GENERANDO".
  - Verify: `npx playwright test generation-banner.spec.ts`
  - Files: `frontend/tests/e2e/generation-banner.spec.ts`
- [x] **Checkpoint S5:** suites completas. **Resueltos: "GENERANDO" poco visible y "Ver progreso" que no hace nada.**
  - Implementado / notas:
    - `event-bus.js`, `generation-banner.js` y `footer.js` se cargan en `<head>` con `defer`: bajo hx-boost el head no se re-ejecuta, así que la conexión SSE sobrevive a las navegaciones (1 sola por pestaña, verificado en E2E) y los listeners no se acumulan.
    - Verificación visual (captura): con `sticky top-0` la banda quedaba 48 px abajo y tapaba el título (`<main>` tiene `p-12` y Chrome mide el sticky desde el borde del padding); se usa `-top-12`.
    - La banda muestra "lista/falló" solo para jobs vistos en vivo en la pestaña; los `recent` del snapshot no se muestran (evita avisos viejos al recargar).
    - El pie conserva "Actividad" (último evento de jobs) sin polling.
    - **Tailwind**: `content` no escaneaba `public/js/`: clases usadas solo en scripts no existían en el CSS (el punto verde/rojo del Core nunca cambió de color; `animate-pulse` de la sala no animaba). Se agregó `./public/js/**/*.js`. Además, los colores `forge` son `var()` sin canal alfa, así que `bg-forge-accent/15` y similares no generan nada: la banda usa `color-mix()` en `globals.css`.
    - E2E: `relatos.spec.ts` esperaba `networkidle`, que nunca llega con una conexión SSE abierta; ahora espera el elemento. `cutover-no-cdn.test.ts` exigía exactamente 1 script en `<head>`; ahora verifica su intención (el único externo es HTMX, el resto son `/js/*` propios).

### S6 — Botones en estado ocupado + guardar/generar desacoplados

- [x] **T6.1:** `generation-guard.js`.
  - Acceptance: todo `[data-generation-trigger]` al hacer submit/click deshabilita todos los triggers de la página, muestra spinner + `data-busy-label` en < 100 ms; se restaura en `pageshow` con `persisted`; escucha `forge:job-started` / `forge:job-done` / `forge:job-failed` de su `data-story-id`.
  - Files: `frontend/public/js/generation-guard.js`, `layout.ejs`
- [x] **T6.2:** Marcar los botones.
  - Acceptance: "Generar/Regenerar/Reintentar/Comenzar" en `gallery.ejs`, `historia.ejs` y `streaming-room.ejs` con `data-generation-trigger`, `data-story-id` y `data-busy-label`.
  - Files: esas 3 vistas
- [x] **T6.3:** Estado inicial server-side.
  - Acceptance: si la historia tiene un job activo, los botones se renderizan deshabilitados como "Generando…" con link "Ver progreso".
  - Files: `historia.controller.ts`, `historia.ejs`, `wizard.controller.ts`, `wizard-confirm.ejs`
- [x] **T6.4:** Express crea el job y maneja el 409.
  - Acceptance: `generarDesdeHistoria` hace `POST /jobs` y redirige a la sala; ante 409 redirige a la sala del job existente, sin mostrar error. Se mantiene la confirmación de regeneración (Spec-219).
  - Files: `historia.controller.ts`
- [x] **T6.4b:** Wizard termina en "Guardar historia" (§2.5).
  - Acceptance: `wizard-confirm.ejs` muestra solo "Guardar historia"; POST/PATCH explícito; éxito → galería con aviso y tarjeta resaltada; error del Core → visible en la confirmación; `submitStep` ya no guarda en silencio al pasar el último paso; se elimina `POST /generar/submit` y `submitGeneration`.
  - Verify: Vitest del controller (éxito, 422, Core caído) + Playwright del flujo completo del wizard.
  - Files: `wizard.controller.ts`, `stream.controller.ts`, `wizard-confirm.ejs`, `routes/index.ts`, `gallery.ejs`, `gallery.controller.ts`
- [x] **T6.4c:** Generar desde la galería.
  - Acceptance: tarjetas `draft`/`pending`/`failed` con "Generar"/"Reintentar" y `completed` con "Regenerar", todas con `data-generation-trigger`; con un job activo la tarjeta muestra "Generando · Acto N/5" en vivo (`forge:job-progress`) y "Ver avance"; al terminar se actualiza el badge de estado sin recargar.
  - Verify: Playwright con backend mock.
  - Files: `gallery.ejs`, `frontend/public/js/generation-banner.js` (o `gallery.js`)
- [x] **T6.5:** E2E de botones.
  - Acceptance: doble click en "Generar historia" → 1 solo POST (contado con `page.on("request")`); volver atrás desde la sala → botón utilizable.
  - Files: `frontend/tests/e2e/generation-guard.spec.ts`
- [x] **Checkpoint S6:** suites completas. **Resueltos: botón que sigue habilitado; guardar y generar desacoplados.**
  - Implementado / notas:
    - `generation-guard.js` en `<head>`: el disparador se marca "pendiente" en el mismo tick del click/submit (un doble click dispara los dos eventos antes de cualquier `setTimeout`; con el bloqueo diferido pasaban 2 POST). El cambio visual se aplica en el tick siguiente.
    - Galería en vivo: se recarga (`htmx.ajax` + `select`) con el **primer avance** del job, no con `job_started`: en ese instante la historia todavía figura `completed`/`draft`.
    - Ficha: estado "Generando… + Ver progreso" con job en curso; se eliminó el botón "Comenzar" (`?start=1`, código muerto que además quedaba roto tras S4).
    - Wizard: el último paso dice "Revisar" (ya no guarda); la confirmación solo tiene "Guardar historia" (`POST /generar/guardar`); errores del Core visibles (incluye 422 de Pydantic). Se eliminaron `POST /generar/submit` y `submitGeneration`.
    - Pendiente de decisión: `PATCH /stories/{id}` solo permite editar borradores ("Solo se pueden editar historias en estado draft"). Antes el wizard tragaba ese error; ahora se muestra.

### S7 — Regenerar acto como job

- [x] **T7.1:** `kind=regenerate_voz` en `JobManager`.
  - Acceptance: envuelve `RegenerateBeatVozUseCase`; `params = {beat, narrative_id}`; publica `job_started` → `job_progress(stage=voz, beat=N)` → `job_done` con `narrative_id`; misma idempotencia por historia.
  - Verify: tests del job con mock LLM.
  - Files: `job_manager.py`, `tests/unit/application/services/test_job_manager.py`
- [x] **T7.2:** API.
  - Acceptance: `POST /stories/{id}/jobs` acepta `{kind: "regenerate_voz", beat, narrative_id}` con validación (400 si falta algo); se elimina `POST /stories/{id}/beats/{n}/regenerate-voz` síncrono y se migran sus tests.
  - Files: `job_router.py`, `beat_router.py`, `tests/unit/presentation/routers/test_beat_router.py`
- [x] **T7.3:** Frontend de relatos.
  - Acceptance: `regenerarActoAction` hace POST → 202 y devuelve el panel en estado "Regenerando acto N…" (con `data-job-id`); con `forge:job-done` de ese job, `htmx.ajax` recarga solo ese panel; con `forge:job-failed`, muestra el error en el panel.
  - Files: `frontend/src/controllers/relatos.controller.ts`, `core_api.service.ts`, `partials/relato_panel.ejs`, `frontend/public/js/relatos.js`
- [x] **T7.4:** E2E.
  - Acceptance: el request de regenerar vuelve en < 500 ms; el panel se actualiza solo; los tests de `relatos.spec.ts` y `relatos-switcher.spec.ts` siguen pasando.
  - Files: `frontend/tests/e2e/relatos.spec.ts`
- [x] **Checkpoint S7:** suites completas. **D2 cerrado.**
  - Implementado / notas:
    - Validación inmediata en `POST /jobs` (`regenerate_voz`): faltan `beat`/`narrative_id` → 422; acto no narrado → 422; relato inexistente o de otra historia → 404; otro job activo → 409.
    - Cancelar un `regenerate_voz` **no** marca la historia `failed` (solo la generación completa la deja a medias). El payload global incluye `params` (acto) para la banda.
    - El panel responde con "Regenerando el acto N…" atado al job (`data-refresh-on-job`) y se recarga con `GET /historia/:id/relatos/:narrativeId/panel` (con `?error=` si falla). Si el job termina antes de que el panel llegue al DOM, se recarga al insertarse (`htmx:afterSwap`).
    - La banda muestra "Regenerando el acto N" y "Ver progreso" lleva a la vista de relatos (no a la sala).
    - Visto en el seed de dev: el relato "Test Spec430" de "El monte prohibido" no tiene acto 2 (beat 2 `pending`, restos de pruebas de Spec-430). El E2E usa los actos existentes.

### S8 — Limpieza y documentación

- [x] **T8.1:** Eliminar `StreamSessionManager`.
  - Acceptance: se borran `stream_session_manager.py` y sus tests (los escenarios útiles de `tests/integration/test_stream_broadcaster.py` quedan migrados a `JobManager`); no quedan imports.
  - Resultado: borrados `stream_session_manager.py`, `test_stream_session_manager.py` (incluye los 2 `xfail` de S0, cuyas versiones contra `JobManager` pasan) y `test_stream_broadcaster.py` (productor único, replay, fan-out y error ya cubiertos por `test_job_manager.py` y `test_event_bus.py`).
  - Verify: `grep -rn stream_session_manager src tests` vacío; `make test`.
- [x] **T8.2:** Decidir `/system/events`.
  - Acceptance: si solo lo usa `/debug`, se mantiene y se documenta; si nadie lo usa, se elimina.
  - Resultado: nadie lo usaba (el pie lo consultaba hasta S5; `/debug` no) → **eliminado**. `observability.record()` se mantiene porque además escribe en el log.
- [x] **T8.3:** Documentación.
  - Acceptance: `CLAUDE.md` (*Web & Streaming*, *Data Flow*, *API Endpoints*, tablas de *Database*) actualizado; Spec-210/220 con nota "reemplazado por Spec-460"; Spec-460 → `DONE` con el checklist tildado.
- [x] **Checkpoint final:** `make lint`, `make test`, `cd frontend && npm test && npx playwright test`, y prueba manual completa en `storymaker.test`.

### Checklist de criterios de aceptación (§3)

- [x] Recargar la sala 5 veces → 1 solo job (T4.6)
- [x] `POST /jobs` con job activo → 409 + redirección (T3.1, T6.4)
- [x] Regenerar acto vuelve en < 500 ms (T7.4)
- [x] Banda en < 1 s sin polling (T5.7)
- [x] Cerrar pestaña a mitad → el job termina; "Regenerar" crea job nuevo (T2.7)
- [x] Reinicio del Core → job `failed` "interrumpida" (T1.4, T2.8)
- [x] Reconexión con `Last-Event-ID` sin duplicados (T3.3)
- [x] Botón ocupado < 100 ms, doble click = 1 POST (T6.5)
- [x] Sin jobs no aparece "GENERANDO" (T5.7)
- [x] Wizard guarda con error visible; generar solo desde galería/ficha (T6.4b, T6.4c)
- [x] "Ver progreso" siempre navega (T5.7)

---

## BOUNDARIES

- **Siempre:** las 5 restricciones de Spec-201; ningún GET dispara trabajo.
- **Consultar antes:** agregar dependencias (Redis, htmx-ext-sse); cambiar el modelo de workers de uvicorn.
- **Nunca:** scripts de migración (`init_db()` + recrear `stories.db`).

---

## DECISIONES (2026-09-22)

- Jobs **persistidos en DB** (`generation_job`).
- `GET /stories/{id}/stream` queda como **alias de solo lectura** durante la transición.
- Orden de implementación: **460 → 440**.
- Stack: solo tecnologías ya presentes (§0); sin dependencias nuevas.
- Uso previsto: 1-2 personas, una pestaña por sesión. Alcanza con **una conexión SSE por pestaña**; se descarta la variante `BroadcastChannel` y no hace falta verificar HTTP/2.
