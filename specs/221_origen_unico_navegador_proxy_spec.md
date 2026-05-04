# Spec-221: Origen Único del Navegador — Proxy `/api/*` en Express y URLs relativas

## Estado

IMPLEMENTADO (sin Slice E) — T0, A, B, C, D completos. 10/10 tests vitest verdes. CA1, CA3, CA5, CA6 verificados automáticamente (HTML sin URLs absolutas, SSE sin buffering, passthrough GET/POST/PATCH/DELETE, suite de tests verde). CA2 y CA4 verificados con smoke multi-host manual (2026-05-04) desde otra máquina de la LAN. Slice E (nginx con `/api/`) queda diferido como mejora opcional sin scope activo.

---

## Objetivo

Eliminar la dependencia del frontend renderizado (EJS + JS) sobre el host concreto donde corre el backend FastAPI. **El navegador debe ver un único origen** (el del frontend Express, sea cual sea el hostname/IP/puerto que el cliente usa) y todas las llamadas al backend (REST + SSE) deben viajar por **URLs relativas** que Express proxia internamente al `CORE_API_URL`.

Resultado esperado: cualquier persona en la red LAN (o detrás del reverse proxy nginx) puede acceder a `http://<lo-que-sea>:3000` (o `https://storymaker.local`) y disparar una generación end-to-end sin que la URL del EventSource se rompa por una diferencia entre el host del navegador y el host del servidor.

---

## Problema

### Síntoma observado (2026-05-04, historia `1a4deb91-ca10-4053-8c17-0e8ed7379479`)

Una clienta en otra máquina de la LAN intentó generar la historia "La ofrenda". Logs del backend (`docker logs narrative-api`) muestran:

```
POST  /api/v1/stories?action=save              → 201 Created
PATCH /api/v1/stories/1a4deb91-…/status        → 200 OK
GET   /api/v1/stories/1a4deb91-… (×N)          → 200 OK   (carga de la sala SSE)
GET   /api/v1/stories/1a4deb91-…/beats         → 200 OK   (sin beats)
GET   /api/v1/stories/1a4deb91-…/stream        ← ❌ NUNCA OCURRIÓ
```

La historia quedó atascada en `status='processing'` con **0 beats, 0 anchors**. La Spec-220 (`StreamSessionManager`) requiere que el primer cliente abra el endpoint `/stream` para que el broadcaster arranque el productor. Como el `EventSource` del navegador nunca llegó al backend, el productor nunca corrió.

### Causa raíz — `frontend/src/services/core_api.service.ts:42-47`

```ts
export function streamUrl(storyId: string): string {
  // El stream se ejecuta en el navegador, necesita localhost
  const browserUrl = process.env.CORE_API_URL?.replace("host.docker.internal", "localhost")
    ?? "http://localhost:8010";
  return `${browserUrl}/api/v1/stories/${storyId}/stream`;
}
```

El frontend Express embebe esta URL **literalmente** en el HTML (`streaming-room.ejs:99` y `:413`). Cuando el cliente accede al frontend desde una máquina distinta al servidor, el `localhost:8010` que ve el navegador es **el localhost de su propia laptop**, donde no hay backend. El `EventSource` falla en silencio (`onerror`) y el `StreamSessionManager` jamás recibe el `attach`.

### Por qué el comentario "necesita localhost" estaba mal desde el origen

El supuesto era: "el frontend corre en Docker, así que el host del backend `host.docker.internal` no aplica al navegador". El reemplazo a `localhost` solo funciona si **navegador y servidor son la misma máquina**, escenario válido en desarrollo solo. El supuesto no se hizo explícito en código ni en spec, y se materializó como bug latente que solo aparece cuando un segundo cliente entra a la LAN.

### Otros lugares afectados

`grep -rn "CORE_URL\|STREAM_URL\|coreStreamUrl"` en `frontend/src/views/`:

| Archivo | Línea | Uso de URL absoluta hacia backend |
|---|---|---|
| `streaming-room.ejs` | 99 | `MONITOR_STREAM_URL` para `EventSource` |
| `streaming-room.ejs` | 413 | `STREAM_URL` para `EventSource` |
| `streaming-room.ejs` | 553-559 | `fetch ${CORE_URL}/stories/.../status` (cancel) |
| `streaming-room.ejs` | 604-610 | `fetch ${CORE_URL}/stories/.../status` (regenerate) |

Todos los puntos de llamada cliente→backend desde JS embebido replican el mismo patrón. Cualquier corrección parcial (ej. solo arreglar `streamUrl`) deja superficies con el mismo bug.

### Impacto en la idempotencia de Spec-220

Spec-220 garantiza que un único productor LLM corre por `story_id`. Pero ese productor se dispara **al primer `attach`**, que ocurre cuando llega el primer `GET /stream`. Si el navegador no puede alcanzar `/stream`, **toda la cadena Spec-220 queda inerte**: la sala muestra MODO MONITOR (porque `status='processing'`) pero nadie la genera. El usuario ve un spinner indefinido sin diagnóstico.

---

## Principios arquitectónicos aplicados

| Principio | Cómo se aplica en este refactor |
|---|---|
| **DIP** (Dependency Inversion) | El cliente HTML no depende de la implementación concreta del backend (host, puerto, esquema). Depende de una **abstracción de origen** ("misma URL que sirve este HTML") y un **contrato de paths** (`/api/v1/...`). |
| **DRY** (Don't Repeat Yourself) | La construcción de URLs hacia el backend deja de duplicarse en `streamUrl()`, en JS inline, en lógica de cancelación, etc. Un único patrón: ruta relativa empezando con `/api`. |
| **KISS** (Keep It Simple) | Cero lógica de "¿estoy en Docker? ¿cuál es mi hostname público?" en frontend. El navegador resuelve la URL contra `window.location.origin` automáticamente. |
| **SRP** (Single Responsibility) | Express asume **una nueva responsabilidad explícita**: ser el único punto de entrada del navegador, proxiando `/api/*` al backend. Esa responsabilidad vive en un middleware aislado, no se mezcla con los controllers. |
| **OCP** (Open/Closed) | Añadir nuevos endpoints REST/SSE no requiere tocar la capa de proxy: el patrón `/api/*` los cubre por convención. |
| **Boundary integrity** (Clean Arch) | El frontend Express era ya el "presentador" del cliente. Antes filtraba parcialmente (renderiza HTML, expone API absoluta). Ahora cierra la frontera: **toda** la comunicación del cliente pasa por él. |

---

## Decisiones de diseño cerradas

| # | Decisión | Justificación |
|---|---|---|
| **D1** | El navegador **siempre** habla con el origen del HTML servido (Express). Cero referencias hardcoded a hosts/puertos del backend en el HTML/JS entregado. | Same-origin → cero CORS, cero mixed-content, portable a cualquier hostname/IP. |
| **D2** | Express monta un middleware de proxy en `/api/*` que reenvía al `CORE_API_URL` (server-to-server, dentro de la red Docker). Implementación: `http-proxy-middleware`. | Librería estándar, mantenida, soporta SSE de fábrica. Alternativa "escribir el proxy a mano" se descarta por costo/riesgo (KISS). |
| **D3** | El proxy se registra **antes de cualquier middleware de body parsing y compresión** y con `selfHandleResponse: false`. Para SSE, se desactiva buffering y compresión en ese path. | El body parsing rompe streams; la compresión (gzip) bufferea y rompe SSE. |
| **D4** | `streamUrl()` se elimina. El JS embebido construye URLs como literales `/api/v1/stories/${id}/stream`. | Una sola convención. Si en el futuro hace falta versionar el path, vive en una constante de un solo lugar. |
| **D5** | `process.env.CORE_API_URL` sigue existiendo, pero pasa a ser **server-only**: lo usan los controllers Express para llamadas SSR (`historiaPage`, `streamingRoomPage`, etc.). El navegador nunca lo ve. | Separación clara entre "URL interna server↔server" y "URL del cliente". |
| **D6** | El backend FastAPI **no se toca**. Sigue corriendo en `8010`, sigue exponiendo `/api/v1/*` tal cual. | Reduce superficie de cambio. El refactor es exclusivamente del frontend. |
| **D7** | Sin breaking changes intermedios. Cada slice deja el sistema funcional para el flujo "navegador y servidor en la misma máquina". El fix multi-host se completa al final del último slice. | Permite mergear slices independientes y revertir si algo falla. |
| **D8** | El reverse proxy nginx (`/home/rick/LLM/apps/reverse_proxy`) **se actualiza en un slice opcional al final**, agregando `storymaker.local/api/` → `host.docker.internal:8010` con `proxy_buffering off` para SSE. | Permite acceso HTTPS uniforme bajo dominio único. **No es prerrequisito** del fix: con D1-D7 ya funciona acceso LAN por IP/puerto sin nginx. |

---

## Arquitectura

### Estado actual (roto en multi-host)

```
┌───────────────────────┐        ┌──────────────────────────┐
│  Browser (cliente B,  │        │  Express (narrative-ui)  │
│  laptop en LAN)       │        │  http://server-host:3000 │
└──────────┬────────────┘        └────────────┬─────────────┘
           │                                  │
           │  GET / (HTML de la sala)         │  SSR: render EJS
           │  con coreStreamUrl =             │   coreStreamUrl ←
           │  "http://localhost:8010/.../stream" │  streamUrl() ← env
           │ ◄────────────────────────────────│
           │                                  │
           │ EventSource("http://localhost:8010/.../stream")
           │ ❌ apunta al localhost del navegador (laptop B)
           │    donde no hay backend
           ▼
        (fail silencioso, productor nunca arranca)

                                              ┌──────────────────────────┐
                                              │  FastAPI (narrative-api) │
                                              │  http://host:8010        │
                                              └──────────────────────────┘
                                                  ▲ recibe SSR pero
                                                  │ NUNCA recibe SSE
```

### Estado objetivo (multi-host robusto)

```
┌──────────────────────┐       ┌──────────────────────────┐       ┌──────────────────────────┐
│  Browser (cualquier  │       │  Express (narrative-ui)  │       │  FastAPI (narrative-api) │
│  cliente en LAN)     │       │  http://<host>:3000      │       │  http://host.docker:8010 │
└──────────┬───────────┘       └────────────┬─────────────┘       └────────────┬─────────────┘
           │                                │                                  │
           │ GET / (HTML)                   │                                  │
           │ ───────────────────────────────►                                  │
           │ ◄────────────────────────────── HTML con paths relativos          │
           │  (sin host backend embebido)   │                                  │
           │                                │                                  │
           │ EventSource("/api/v1/.../stream")                                  │
           │ ───────────────────────────────►                                  │
           │                                │  http-proxy-middleware           │
           │                                │  /api/* → CORE_API_URL           │
           │                                │ ────────────────────────────────►│
           │                                │                                  │  StreamSessionManager
           │                                │                                  │  attach + producer arranca
           │                                │ ◄──────────────────────── SSE   │
           │ ◄──────────────────────── SSE  │  (sin buffering)                 │
           │                                │                                  │
```

### Componentes nuevos / modificados

| Componente | Cambio |
|---|---|
| `frontend/src/middleware/api_proxy.ts` | **NUEVO**. Encapsula la configuración de `http-proxy-middleware` (SSE-friendly, sin compresión). |
| `frontend/src/index.ts` (o `app.ts`) | Registra el middleware antes de body parsers / compresión. |
| `frontend/src/services/core_api.service.ts` | `streamUrl()` se **elimina**. `CORE_API_URL` queda solo para uso interno del controller (SSR). |
| `frontend/src/controllers/stream.controller.ts` | Pasa al view una URL relativa en `coreStreamUrl`. |
| `frontend/src/views/streaming-room.ejs` | Todas las URLs JS hacia backend pasan a relativas: `EventSource("/api/v1/.../stream")`, `fetch("/api/v1/.../status")`. |
| `frontend/package.json` | Añade dependencia `http-proxy-middleware` (~3.0). |
| `reverse_proxy/nginx_config/default.conf` *(opcional, Slice E)* | Añade location `/api/` con `proxy_buffering off` y `proxy_read_timeout` largo. |

---

## Slices (incrementales, sin breaking changes)

### Slice A — Middleware de proxy `/api/*` en Express (no rompe nada)

**Objetivo:** introducir el proxy sin que ningún cliente todavía lo use. Acceder a `http://localhost:3000/api/v1/health` debe responder lo mismo que `http://localhost:8010/api/v1/health`.

**Archivos:**
- `frontend/package.json`: añadir `http-proxy-middleware: ^3.0.0`.
- `frontend/src/middleware/api_proxy.ts` (nuevo): exporta `createApiProxy(coreApiUrl: string): RequestHandler` con:
  - `target: coreApiUrl`
  - `changeOrigin: true`
  - `pathRewrite: { '^/api': '/api' }` (no-op explícito; documentación)
  - `selfHandleResponse: false`
  - `on.proxyReq`: log mínimo (path + method) en dev
  - SSE: `proxyTimeout: 0`, `timeout: 0`
- `frontend/src/index.ts`: importar y registrar `app.use('/api', createApiProxy(CORE_API_URL))` **antes de** cualquier `express.json()` / compression.

**Sin tocar:** controllers, views, `streamUrl()`. El proxy existe pero el HTML sigue mandando al cliente la URL absoluta vieja.

**Tests:**
- Unitario `tests/unit/middleware/api_proxy.test.ts`:
  - `proxy_forwards_GET_to_target`
  - `proxy_preserves_headers`
  - `proxy_does_not_buffer_chunked_response`
- Smoke manual: `curl http://localhost:3000/api/v1/health` ≡ `curl http://localhost:8010/api/v1/health`.

### Slice B — JS embebido del SSE pasa a URL relativa

**Objetivo:** cerrar el bug visible. El `EventSource` deja de apuntar al host absoluto.

**Archivos:**
- `frontend/src/services/core_api.service.ts`: borrar `streamUrl()`.
- `frontend/src/controllers/stream.controller.ts`:
  - `streamingRoomPage` ahora pasa `coreStreamUrl = '/api/v1/stories/${storyId}/stream'` (literal relativo).
  - El nombre `coreStreamUrl` se conserva por compatibilidad con el view; se podría renombrar a `streamPath` en un cleanup posterior.
- `frontend/src/views/streaming-room.ejs`:
  - `MONITOR_STREAM_URL` (línea 99) y `STREAM_URL` (línea 413) reciben el path relativo desde el controller. **Sin cambios estructurales** en el JS.

**Tests:**
- Unitario `tests/unit/controllers/stream.controller.test.ts`:
  - `streamingRoomPage_passes_relative_path_to_view` (mockear axios, verificar `render` args).
- Smoke 2 máquinas: cliente desde otra IP → DevTools muestra `EventSource` pegando a `http://<server>:3000/api/v1/.../stream`; backend `narrative-api` registra el `GET /stream`.

### Slice C — Restantes `fetch()` en JS embebido a URL relativa

**Objetivo:** completar la migración. Quedan los `fetch()` de cancel y regenerate.

**Archivos:**
- `frontend/src/views/streaming-room.ejs`:
  - `cancelGeneration()` (línea ~553): cambiar `${CORE_URL}/stories/.../status` por `/api/v1/stories/${STORY_ID}/status`.
  - `initiateRegeneration()` (línea ~604): mismo cambio.
  - Eliminar la variable local `CORE_URL = STREAM_URL.replace(...)` que ya no aplica.

**Tests:**
- Smoke 2 máquinas: cancel + regenerate funcionan desde cliente remoto.
- Test de regresión: el regenerate previo (`9e36aee4`) sigue funcionando localhost.

### Slice D — Tests de integración del proxy con SSE

**Objetivo:** garantizar que el proxy no introduce buffering/latencia que rompa la experiencia SSE.

**Archivos:**
- `frontend/tests/integration/proxy_sse.test.ts` (nuevo):
  - Levanta un backend mock que stream-ea 5 eventos con 100ms de gap.
  - Levanta Express con el proxy.
  - Cliente HTTP fetch a `/api/v1/...` y mide:
    - Tiempo entre `chunk` recibidos (debe ser ~100ms, no 500ms si hubiera buffering).
    - Headers preservados (`content-type: text/event-stream`).
- `frontend/tests/integration/proxy_passthrough.test.ts`:
  - Verifica métodos: GET, POST, PATCH, DELETE.
  - Verifica códigos: 200, 201, 404, 500 propagados sin alterar.

### Slice E *(OPCIONAL)* — Reverse proxy nginx con dominio único

**Objetivo:** habilitar `https://storymaker.local` como punto único, con `/api/*` ruteado al backend (sin pasar por Express). Esto es **opcional** y solo se justifica si querés HTTPS uniforme + dominio único en LAN.

**Archivos:**
- `/home/rick/LLM/apps/reverse_proxy/nginx_config/default.conf`: agregar dentro del `server { server_name storymaker.local; ... }`:
  ```nginx
  location /api/ {
      proxy_pass http://host.docker.internal:8010;
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

      # SSE: streaming sin buffering
      proxy_buffering off;
      proxy_cache off;
      proxy_read_timeout 1h;
      proxy_send_timeout 1h;
      chunked_transfer_encoding on;
  }
  ```
- Reiniciar `mi_reverse_proxy`.

**Decisión arquitectónica cerrada:** **dos rutas válidas** dejan acceso multi-host funcionando:
- **Express proxy** (D1-D7): obligatorio. Resuelve el bug y funciona sin nginx.
- **nginx con `/api/`** (D8): aditivo, da HTTPS y dominio único.

Si elegís ambas, el navegador puede apuntar a `https://storymaker.local/api/...` (nginx → backend directo) **o** a `http://server:3000/api/...` (Express → backend). Ambos llegan al mismo `narrative-api`.

---

## Tareas (checklist)

> Reglas SDD: marcar cada item como `- [x]` al completarlo. No avanzar de slice sin OK explícito del usuario tras el smoke verification del slice anterior.

### Slice A — Proxy en Express

- [ ] **T1.** Agregar `http-proxy-middleware` a `frontend/package.json` y correr install.
- [ ] **T2.** Crear `frontend/src/middleware/api_proxy.ts` con la factory `createApiProxy(coreApiUrl)`.
- [ ] **T3.** Registrar el middleware en `frontend/src/index.ts` antes de body parsers / compression.
- [ ] **T4.** Escribir 3 tests unitarios en `frontend/tests/unit/middleware/api_proxy.test.ts`.
- [ ] **T5.** Verify: `curl http://localhost:3000/api/v1/health` devuelve `{"status":"healthy",...}` igual que el backend directo.
- [ ] **T6.** Verify: `npm test` en frontend pasa los 3 tests nuevos.

**Sign-off A:** OK del usuario tras `curl` exitoso.

### Slice B — `EventSource` con path relativo

- [ ] **T7.** Borrar `streamUrl()` en `frontend/src/services/core_api.service.ts`.
- [ ] **T8.** Modificar `streamingRoomPage` en `stream.controller.ts` para pasar `coreStreamUrl = '/api/v1/stories/${storyId}/stream'`.
- [ ] **T9.** Confirmar que `streaming-room.ejs` (líneas 99, 413) consume el valor sin cambios estructurales.
- [ ] **T10.** Test unitario `streamingRoomPage_passes_relative_path_to_view`.
- [ ] **T11.** Smoke: desde la laptop de otro cliente en la LAN, `http://<server-ip>:3000/galeria` → click "Generar" → la sala arranca, beats se renderizan en vivo.
- [ ] **T12.** Verify: `docker logs narrative-api | grep "/stream"` muestra el `GET .../stream` con el `story_id` nuevo.

**Sign-off B:** OK del usuario tras smoke multi-host.

### Slice C — `fetch()` con path relativo

- [ ] **T13.** Migrar `cancelGeneration()` en `streaming-room.ejs` a path relativo.
- [ ] **T14.** Migrar `initiateRegeneration()` en `streaming-room.ejs` a path relativo.
- [ ] **T15.** Eliminar la variable local `CORE_URL` derivada de `STREAM_URL`.
- [ ] **T16.** Smoke: desde cliente remoto, regenerar una historia `completed` → ver el flujo end-to-end.
- [ ] **T17.** Smoke: durante una generación, click "Detener" → status pasa a `failed` y la sala muestra el panel de cancelación.

**Sign-off C:** OK del usuario tras smokes regenerate + cancel.

### Slice D — Tests de integración

- [ ] **T18.** Crear `frontend/tests/integration/proxy_sse.test.ts` con backend mock que stream-ee 5 eventos.
- [ ] **T19.** Crear `frontend/tests/integration/proxy_passthrough.test.ts` (GET/POST/PATCH/DELETE).
- [ ] **T20.** Verify: `npm test` pasa todos los integration tests.
- [ ] **T21.** Verify: el test SSE confirma que el delta entre chunks es ≤ 200ms (sin buffering).

**Sign-off D:** OK del usuario tras suite verde.

### Slice E *(opcional)* — nginx con `/api/`

- [ ] **T22.** Agregar el bloque `location /api/` al `default.conf` de `reverse_proxy`.
- [ ] **T23.** `docker compose restart` del reverse proxy.
- [ ] **T24.** Verify: `curl -k https://storymaker.local/api/v1/health` responde 200.
- [ ] **T25.** Smoke: cliente accede a `https://storymaker.local`, genera una historia, todo el SSE viaja por nginx.
- [ ] **T26.** Documentar en `README.md` del proyecto que hay dos rutas de acceso (Express directo + nginx HTTPS).

**Sign-off E:** OK del usuario tras smoke con HTTPS.

---

## Tests

### Unitarios

```ts
// frontend/tests/unit/middleware/api_proxy.test.ts
describe("createApiProxy", () => {
  it("forwards GET requests to the target", async () => { /* ... */ });
  it("preserves response headers", async () => { /* ... */ });
  it("does not buffer chunked responses", async () => { /* ... */ });
});

// frontend/tests/unit/controllers/stream.controller.test.ts
describe("streamingRoomPage", () => {
  it("passes a relative path to the view as coreStreamUrl", async () => {
    const res = mockResponse();
    await streamingRoomPage(mockRequest({ storyId: "x" }), res);
    expect(res.render).toHaveBeenCalledWith(
      "streaming-room",
      expect.objectContaining({ coreStreamUrl: "/api/v1/stories/x/stream" })
    );
  });
});
```

### Integración

```ts
// frontend/tests/integration/proxy_sse.test.ts
it("streams SSE events without buffering through the proxy", async () => {
  const backend = startMockBackend({ emitEvents: 5, gapMs: 100 });
  const express = startExpressWithProxy(backend.url);
  const reader = await fetchEventStream(`${express.url}/api/v1/test/stream`);
  const timestamps = await reader.collect(5);
  const deltas = pairwiseDeltas(timestamps);
  expect(Math.max(...deltas)).toBeLessThanOrEqual(200);  // no buffering
});

// frontend/tests/integration/proxy_passthrough.test.ts
it.each(["GET", "POST", "PATCH", "DELETE"])(
  "forwards %s requests transparently",
  async (method) => { /* ... */ },
);
```

### Smoke manual

| # | Smoke | Esperado |
|---|---|---|
| S1 | Cliente en LAN (otra IP) abre `http://<server>:3000/galeria` y genera | Beats aparecen en vivo, historia se completa |
| S2 | Mismo cliente click "Detener" durante generación | Status `failed`, panel de cancelación visible |
| S3 | Mismo cliente regenera una historia `completed` | Pipeline se reinicia, beats viejos se reemplazan |
| S4 | Dos clientes simultáneos al mismo `story_id` | Ambos ven los mismos eventos (Spec-220 sigue garantizando 1 productor) |
| S5 *(opcional)* | Cliente accede a `https://storymaker.local` | Idem S1-S4 sobre HTTPS |

---

## Criterios de Aceptación

| # | Criterio | Verificación |
|---|---|---|
| **CA1** | El HTML servido por Express **no contiene** ninguna URL absoluta hacia `localhost:8010`, `host.docker.internal:8010` ni similares | `curl http://localhost:3000/generar/stream/<id> \| grep -E 'localhost:8010\|host.docker.internal:8010'` → **vacío** |
| **CA2** | Un cliente en otra máquina de la LAN puede generar end-to-end | Smoke S1 verde |
| **CA3** | El proxy preserva el `Content-Type: text/event-stream` y entrega chunks con el mismo timing del backend | Test integración delta ≤ 200ms |
| **CA4** | Cancel + regenerate funcionan desde cliente remoto | Smokes S2, S3 verdes |
| **CA5** | Spec-220 sigue válido: dos clientes al mismo `story_id` = un productor | Smoke S4 verde + tests integración Spec-220 siguen verdes |
| **CA6** | `pytest tests -v` (backend) y `npm test` (frontend) sin regresiones | CI |
| **CA7** *(opcional)* | Acceso por `https://storymaker.local` funcional | Smoke S5 verde |

---

## Riesgos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| **R1** | `http-proxy-middleware` con SSE bufferea por defecto algún pipeline interno | Media | Alto (rompe UX en vivo) | Test integración mide delta entre chunks; si falla, configurar explícitamente `proxyTimeout: 0`, `selfHandleResponse: false`, y revisar que no haya `compression()` middleware activo en `/api`. |
| **R2** | Algún middleware Express previo (e.g. `express.json()`) consume el body de POST antes de que el proxy lo reenvíe | Media | Alto (POST llegan vacíos al backend) | Registrar el proxy **antes** de body parsers. Test de regresión `test_post_body_is_forwarded`. |
| **R3** | Cambiar `streamUrl()` a path relativo rompe el modo "navegador local + frontend en host" si alguien lo corría sin Docker | Baja | Bajo | El frontend siempre asume un Express delante. Si alguien tenía un setup raro (CLI directo al backend), no afecta — la CLI no usa `streamUrl()`. |
| **R4** | `CORE_API_URL` apunta a `host.docker.internal:8010` desde el container Express, pero la red Docker custom (si llegara a configurarse) podría fallar | Baja | Medio | Mantener `extra_hosts: host.docker.internal:host-gateway` en el `docker-compose.yml` (ya está). |
| **R5** | nginx Slice E con `proxy_buffering off` mal configurado bufferea SSE | Media (si se hace) | Medio | Verificar con `curl -N https://storymaker.local/api/v1/.../stream` que los chunks llegan en tiempo real. |
| **R6** | El path `/api` del frontend Express tiene un futuro endpoint propio (no proxiado) que ahora colisiona | Baja | Bajo | Auditar `frontend/src/routes/index.ts`: hoy los endpoints del frontend viven bajo `/historia/`, `/galeria`, `/generar/`, `/api/historia/...`. **Conflicto detectado:** `/api/historia/:id` (DELETE en `historia.controller.ts:54`) colisionaría con el proxy. Resolver renombrando a `/internal/historia/:id` o moviendo bajo otro prefijo, **antes** de Slice A. Ver T0 abajo. |

### Tarea preliminar derivada de R6

- [ ] **T0.** Antes de Slice A, auditar `frontend/src/routes/index.ts` y renombrar cualquier ruta Express bajo `/api/*` a otro prefijo (p.ej. `/internal/api/*`). Files: `routes/index.ts`, `views/*.ejs` que apunten a esas rutas, `controllers/historia.controller.ts` (HX redirects).

---

## Reversibilidad

- **Slices A-D** son aditivos. `git revert` los vuelve atrás sin pérdida funcional (el sistema queda como hoy: localhost-only).
- **Slice E** es aditivo en infraestructura externa. Quitar el bloque `location /api/` y reiniciar nginx revierte.
- Cero cambios en backend FastAPI.
- Cero cambios de schema DB.
- Cero cambios en CLI.

---

## Open questions

1. **¿Renombramos `coreStreamUrl` a `streamPath`?** El nombre actual sugería URL absoluta. Cambiarlo es cosmético pero clarifica. **Propuesta:** dejarlo para un cleanup post-Slice C, no bloquear el fix.
2. **¿El frontend Express expone su propio middleware de health en `/api/health` para detectar caídas del backend?** Hoy `/api/v1/health` se proxia al backend; si el backend cae, el navegador ve 502/504. **Propuesta:** fuera de scope de este spec; abrir spec separado si surge la necesidad.
3. **¿Slice E (nginx) entra en este spec o se separa?** Como D8 lo declara opcional y aditivo, **se mantiene aquí** como sección opcional para tener todo el contexto en un lugar. Si el usuario decide implementar solo A-D, el spec se cierra como completo igualmente.

---

## Plan técnico

### Hallazgos del research previo al PLAN

| # | Hallazgo | Implicancia |
|---|---|---|
| H1 | `streamUrl()` se invoca solo desde `streamingRoomPage` y se inyecta como `coreStreamUrl` al view. Ningún otro caller. | Cambio acotado. Sin caller orfaneado al borrar la función. |
| H2 | `streaming-room.ejs` tiene 4 puntos de URL absoluta hacia el backend (líneas 99, 413, 553-559, 604-610). | Slice B cubre 99 + 413 (las dos `EventSource`). Slice C cubre los `fetch()` de cancel/regenerate. |
| H3 | `frontend/src/routes/index.ts` ya tiene rutas bajo `/api/historia/...` (DELETE de historia/markdown). Colisión potencial con el prefijo proxy `/api/*`. | T0 obligatoria: renombrar antes de Slice A. |
| H4 | `http-proxy-middleware` v3 soporta SSE de fábrica si no hay `compression` previo y `selfHandleResponse: false`. | Configuración mínima. Tests de integración blindarán contra regresiones. |
| H5 | `docker-compose.yml` mapea `narrative-ui:3000` → `host:3000` y `narrative-api:8010` → `host:8010`. Ambos puertos quedan abiertos. Tras Slice E *(opcional)*, podríamos cerrar el `8010` al exterior — solo accesible vía Express o nginx. | Mejora de superficie: postergar a un spec aparte de seguridad. |
| H6 | Spec-220 (`StreamSessionManager`) está IMPLEMENTADO y depende de que el primer `attach` ocurra. La causa del bug actual es que ese `attach` nunca llega. **221 destrabba 220 sin modificarlo.** | Refactor ortogonal; cero impacto en lógica de broadcaster. |

### Orden de implementación recomendado

1. **T0** (auditoría de colisión `/api/*` en rutas Express) — bloqueante.
2. **Slice A** (proxy infraestructura) — sin tocar UI.
3. **Slice B** (EventSource relativo) — fix visible del bug.
4. **Slice C** (fetch relativos) — completar migración.
5. **Slice D** (tests integración) — blindar contra regresión.
6. **Slice E** *(opcional, paralelizable)* — nginx HTTPS uniforme.

### Paralelización

| Combinación | Posible | Justificación |
|---|---|---|
| A + B en paralelo | No | B depende de A (relativo solo funciona si Express proxia). |
| C + D en paralelo | Sí | Tests integración (D) testean infraestructura A; no bloquean C. |
| E paralelo a B/C/D | Sí | Slice E es de infraestructura externa (nginx), independiente del frontend. |

### Costo estimado

| Slice | Esfuerzo | Tests |
|---|---|---|
| T0 | ~10 min | manual |
| A  | ~40 min | 3 unit |
| B  | ~25 min | 1 unit + smoke |
| C  | ~15 min | smoke |
| D  | ~60 min | 2 integración |
| E *(opc)* | ~20 min | smoke |
| **Total** | **~2.5 h (~3 h con E)** | 6 tests + smokes |

---

## Notas sobre alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **Construir URL absoluta desde `req.headers.host`** en `streamingRoomPage` | Funciona, pero deja al backend expuesto al navegador (puerto 8010 abierto al cliente). Same-origin sigue roto, CORS futuro pendiente. **Viola D1.** |
| **Cambiar `localhost` por `window.location.hostname`** en `streamUrl()` | Asume puerto 8010 público y mismo hostname. Falla con HTTPS, con dominios distintos para front/back, con reverse proxy. Parche, no solución. |
| **Mover todo bajo nginx (sin proxy en Express)** | Requiere nginx obligatoriamente para acceso LAN. Hoy un usuario puede correr `docker compose up` y acceder por IP:3000 sin nginx — no rompamos esa simplicidad. |
| **Servir el frontend estático desde FastAPI directamente** | Refactor mayor, mezcla responsabilidades, rompe la separación Clean Arch presentation/infrastructure. |
| **WebSocket en lugar de SSE** | Refactor enorme con cero ganancia funcional para el caso de uso. SSE ya cumple. |
