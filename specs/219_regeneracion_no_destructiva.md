# Spec-219: Regeneración No Destructiva y Saneamiento UX de Sala

## Estado
IMPLEMENTADO — T1-T5 aplicados. Verificaciones automáticas OK (CA7, EJS balanceados, TypeScript compila). CA1-CA6 + CA8 verificados con smoke manual (2026-05-04) con frontend corriendo y stories en cada estado.

---

## Problema

Tres problemas relacionados detectados sobre el flujo de regeneración de historias `completed`:

1. **Regeneración destructiva prematura.** El click "Regenerar" en galería dispara inmediatamente `PATCH /api/v1/stories/:id/status { status: "processing" }`, que (Spec-216 Slice A) borra `macro_beat`, `narrative_journal`, `narrative_anchors` y el `.md` físico **antes de que el usuario realmente confirme** el inicio de la regeneración. Si el usuario cierra la pestaña entre el click y el "Iniciar generación" de la sala, la historia queda zombi en `processing` con todos los beats borrados, sin posibilidad de recuperación hasta el próximo reinicio del servidor (`recover_processing_stories`).

2. **"Ver avance" en estado `completed` es ruido.** `gallery.ejs:78-83` muestra el botón "Ver avance" para `completed` y `failed`. Para `completed`, el link a `/generar/stream/:id` cae en el bloque MODO LECTURA (`streaming-room.ejs:12-96`) que solo re-muestra los beats existentes — no hay "avance" que ver. El título de la historia y el botón Markdown ya cubren esa lectura.

3. **Sin confirmación visual del costo de regenerar.** Spec-215 eliminó deliberadamente el modal en galería. Combinado con (1), un click descuidado destruye sin advertencia.

---

## Decisiones cerradas

| # | Decisión | Justificación |
|---|---|---|
| **D1** | Limpieza de artefactos se difiere al click "Iniciar regeneración" en la sala. La historia mantiene `completed` hasta ese momento. | Click "Regenerar" se vuelve no destructivo. Cerrar pestaña sin confirmar = sin pérdida. |
| **D2** | Sin modal de confirmación. La sala es la confirmación implícita: el usuario llega ahí sabiendo qué fue a hacer. La pantalla incluye advertencia inline (texto + ícono), no popup. | Honra simplicidad de Spec-215 sin reintroducir modal. |
| **D3** | Quitar "Ver avance" para `completed` en galería. Mantener para `failed` (ahí sí hay beats parciales útiles). | Reduce ruido. La lectura ya está cubierta por título y MD. |
| **D4** | Mantener estado único `processing`. No se introduce `regenerating`. | Misma transición de estado, distinto contexto del cliente. |

---

## Assumptions

| # | Assumption |
|---|---|
| **A1** | Mecanismo para señalar "intent de regenerar" cuando se navega a `/generar/stream/:id` con `status=completed`: **query string `?regenerate=1`**. La sala lo lee y muestra la pantalla "¿Listo para regenerar?". |
| **A2** | El `PATCH /api/v1/stories/:id/status { processing }` (que dispara la limpieza Spec-216) se llama **desde JS del cliente** al hacer click en "Iniciar regeneración", no desde el controller Express. La sala ya tiene infra JS para hablar con Core API. |
| **A3** | Advertencia inline = texto + ícono naranja arriba del botón "Iniciar regeneración". Sin modal, sin overlay. |
| **A4** | Se borra deuda de Spec-215/216: `frontend/src/views/partials/modal_regenerar.ejs`, `modalConfirmarRegenerar` (controller) y la ruta `/modales/confirmar-regenerar/:storyId`. Nadie más los usa tras este spec. |
| **A5** | `failed` y `draft` mantienen el flujo actual de "Regenerar"/"Reintentar"/"Generar" (patch+redirect inmediato). No hay generación valiosa que perder en esos estados. |
| **A6** | El click "Regenerar" desde la sala en MODO LECTURA (`streaming-room.ejs:78-84`) también cambia: hoy abre modal vía HTMX; tras este spec, redirige a `/generar/stream/:id?regenerate=1` (la misma URL en la que ya está, pero forzando el modo regeneración). Equivalente a un reload con flag. |

---

## Solución

### Flujo nuevo

```
[Galería] click "Regenerar" en historia completed
    │  POST /historia/:id/generar
    ▼
[Frontend Express] generarDesdeHistoria
    │  status === 'completed' → NO PATCH. Solo redirect ?regenerate=1
    │  status === 'failed' o 'draft' → flujo actual (PATCH + redirect)
    ▼
[Sala] /generar/stream/:id?regenerate=1
    │  storyStatus = 'completed' + regenerate=1 → renderiza pantalla "¿Listo para regenerar?"
    │  con advertencia inline + botón "Iniciar regeneración"
    ▼
[Usuario] click "Iniciar regeneración"
    │  JS: fetch PATCH /api/v1/stories/:id/status { processing }  ← acá sí limpia (Spec-216)
    │  JS: startStream() — abre EventSource
    ▼
[Backend] SSE pipeline normal
```

### Estado de la historia durante el flujo

| Momento | Status DB | Beats DB |
|---|---|---|
| Antes de click "Regenerar" | `completed` | presentes |
| Tras click "Regenerar", llegando a sala | `completed` (sin cambio) | presentes |
| Click "Iniciar regeneración" | `processing` (recién ahora) | borrados (Spec-216) |
| SSE en curso | `processing` | re-poblándose |
| SSE finaliza | `completed` | nuevos |

---

## Cambios requeridos

### Slice A — Galería: limpieza de botón "Ver avance" para `completed`

**Archivo:** `frontend/src/views/gallery.ejs` (líneas 78-83)

- Cambiar la condición `<% if (s.status === 'completed' || s.status === 'failed') { %>` por `<% if (s.status === 'failed') { %>`.
- "Ver avance" deja de mostrarse para `completed`. La lectura queda cubierta por el link al título y por "Markdown" (descarga).

### Slice B — Controller: regeneración no destructiva

**Archivo:** `frontend/src/controllers/historia.controller.ts` (función `generarDesdeHistoria`, líneas 247-269)

- Antes del PATCH, consultar el status actual de la historia (`GET /api/v1/stories/:id`).
- Si `status === 'completed'`: **omitir el PATCH** y redirigir a `/generar/stream/:id?regenerate=1`.
- Si `status === 'failed' | 'draft'`: comportamiento actual (PATCH `processing` + redirect a `/generar/stream/:id`).

### Slice C — Sala: detectar `?regenerate=1` y exponer pantalla de inicio

**Archivo:** `frontend/src/views/streaming-room.ejs`

- En el header EJS, leer la query string (`regenerate`) y guardarla en una flag local: `const regenerateMode = (req query) === '1' && storyStatus === 'completed'`.
- Cambiar la condición `<% if (storyStatus !== 'processing') { %>` (línea 12) para que cuando `regenerateMode === true` se entre al bloque MODO SSE en lugar de MODO LECTURA.
- Dentro de MODO SSE, el bloque `start-panel` (líneas 147-167) ya tiene rama para `completed`. Reformularla:
  - Mostrar título: "¿Listo para regenerar?"
  - Advertencia inline: ícono naranja + texto que explica que se perderá la generación actual y el MD.
  - Botón: "Iniciar regeneración" (no "Regenerar" que abre modal).
  - El botón llama a `initiateRegeneration()` (nueva función JS).

### Slice D — JS: `initiateRegeneration()`

**Archivo:** `frontend/src/views/streaming-room.ejs` (`<script>` al final)

- Agregar función `initiateRegeneration()`:
  1. Ocultar `start-panel` y mostrar `initial-spinner`.
  2. `fetch PATCH ${CORE_API_URL}/api/v1/stories/${STORY_ID}/status` con `{ status: "processing" }`.
  3. Si OK → `startStream()` (que abre el `EventSource`).
  4. Si falla → mostrar error con `showError(...)`.
- En el bloque MODO SSE (cuando ya `status=processing` por venir de un retry sin regenerate), `initiateGeneration()` actual sigue intacta.

### Slice E — Sala MODO LECTURA: botón "Regenerar" sin modal

**Archivo:** `frontend/src/views/streaming-room.ejs` (líneas 78-84)

- Reemplazar el botón HTMX que abre `/modales/confirmar-regenerar/:storyId` por un link directo a `/generar/stream/<%= storyId %>?regenerate=1`.
- Eliminar atributos `hx-get`, `hx-target`, `hx-swap`.

### Slice G — historia.ejs: link "Comenzar Regenerar" pasa `?regenerate=1`

**Archivo:** `frontend/src/views/historia.ejs` (línea 140)

- Cuando `showStartButton` está activo y `story.status === 'completed'`, el `<a href="/generar/stream/<%= story.id %>">` debe ser `<a href="/generar/stream/<%= story.id %>?regenerate=1">`.
- Si no, el usuario que llega vía "Comenzar Regenerar" desde la vista de historia caería en MODO LECTURA en vez de la pantalla de regen.
- El botón "Regenerar" más abajo (línea 154-161, form POST) ya queda cubierto automáticamente por Slice B (controller no patchea si status=completed).

### Slice F — Limpieza de modal obsoleto

**Archivos a eliminar / modificar:**

- `frontend/src/views/partials/modal_regenerar.ejs` → eliminar archivo.
- `frontend/src/controllers/historia.controller.ts` → eliminar función `modalConfirmarRegenerar`.
- `frontend/src/routes/index.ts` → eliminar ruta `router.get("/modales/confirmar-regenerar/:storyId", modalConfirmarRegenerar)`.
- Verificar que no haya otras referencias HTMX a `confirmar-regenerar`.

---

## Archivos afectados

| Archivo | Tipo de cambio |
|---|---|
| `frontend/src/views/gallery.ejs` | Quitar "Ver avance" para `completed` |
| `frontend/src/controllers/historia.controller.ts` | `generarDesdeHistoria` no patchea si status=completed; eliminar `modalConfirmarRegenerar` |
| `frontend/src/views/streaming-room.ejs` | Detectar `?regenerate=1`; pantalla "¿Listo para regenerar?"; `initiateRegeneration()`; quitar botón con modal en MODO LECTURA |
| `frontend/src/controllers/stream.controller.ts` | `streamingRoomPage` lee `req.query.regenerate` y lo pasa al render context |
| `frontend/src/views/historia.ejs` | Link "Comenzar Regenerar" agrega `?regenerate=1` si status=completed |
| `frontend/src/routes/index.ts` | Eliminar ruta `/modales/confirmar-regenerar/:storyId` y su import |
| `frontend/src/views/partials/modal_regenerar.ejs` | **Eliminar archivo** |

**Sin cambios en backend.** El endpoint `PATCH /api/v1/stories/:id/status` ya está correcto (Spec-216).

---

## Criterios de Aceptación

| # | Criterio | Verificación |
|---|---|---|
| **CA1** | Click "Regenerar" en galería sobre historia `completed` → URL `/generar/stream/:id?regenerate=1` y status DB sigue `completed` | DevTools Network + `sqlite3 data/stories.db "SELECT status FROM story WHERE id='...'"` |
| **CA2** | En la sala con `?regenerate=1`, los beats viejos NO se borraron y se muestra pantalla "¿Listo para regenerar?" con advertencia inline | Inspección visual + query DB |
| **CA3** | Click "Iniciar regeneración" → status pasa a `processing`, beats/journal/anchors/MD se borran y arranca el SSE | DevTools + queries DB durante el flujo |
| **CA4** | Cerrar la pestaña en la sala con `?regenerate=1` antes de hacer click no destruye nada (status sigue `completed`, beats intactos) | Reproducir manualmente |
| **CA5** | Botón "Ver avance" no aparece para historias `completed` en galería; sí aparece para `failed` | Inspección visual con stories en cada estado |
| **CA6** | Click "Regenerar" en sala MODO LECTURA → URL `?regenerate=1` (mismo flujo que galería); modal_regenerar.ejs no se abre | Inspección visual |
| **CA7** | `grep -r "modal_regenerar\|modalConfirmarRegenerar\|confirmar-regenerar" frontend/` devuelve 0 hits | grep |
| **CA8** | Para `failed`: click "Reintentar" mantiene el flujo actual (patch + redirect a sala SSE arrancando) | Reproducir manualmente con historia failed |

---

## Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| **R1** | Usuario navega directo a `/generar/stream/:id?regenerate=1` (URL pegada) sin pasar por "Regenerar" → ve pantalla regen sin contexto | Bajo impacto: el botón sigue requiriendo un click adicional. La pantalla es clara. |
| **R2** | `?regenerate=1` se pierde por refresh F5 del navegador → vuelve a MODO LECTURA. Si el usuario clickeó "Iniciar regeneración" justo antes y refrescó, el patch ya pasó y entra en MODO SSE. | OK: el F5 después de iniciar reanuda correctamente porque ya status=processing. F5 antes de iniciar lleva a MODO LECTURA → click "Regenerar" otra vez → reentry sin daño (era no-destructivo). |
| **R3** | Race condition: dos pestañas abiertas, una en MODO LECTURA y otra en `?regenerate=1`. Click "Iniciar" en una mientras la otra está leyendo. | Aceptable: el patch dispara limpieza, la otra pestaña verá inconsistencia hasta refresh. No es escenario de uso primario. |
| **R4** | El status check extra en el controller (`GET /api/v1/stories/:id` antes del PATCH) agrega latencia | Despreciable (~1 query SQLite). Si pesa, cachear en sesión. |

---

## Open questions

Ninguna pendiente — todas las decisiones cerradas en D1-D4 + A1-A6.

---

## Tareas

- [ ] **T1: Slice A — Quitar "Ver avance" para `completed` en galería**
  - Acceptance: la condición del botón "Ver avance" (`gallery.ejs:78`) cambia de `s.status === 'completed' || s.status === 'failed'` a solo `s.status === 'failed'`.
  - Verify: refrescar `/galeria`; historias `completed` no muestran "Ver avance"; historias `failed` sí.
  - Files: `frontend/src/views/gallery.ejs`.

- [ ] **T2: Slices C+D+E — Sala detecta `?regenerate=1`, expone "Iniciar regeneración" y elimina modal en MODO LECTURA**
  - Acceptance:
    - `stream.controller.ts::streamingRoomPage` lee `req.query.regenerate` y pasa `regenerateMode = (req.query.regenerate === '1' && storyStatus === 'completed')` al render context.
    - En `streaming-room.ejs`: la condición `<% if (storyStatus !== 'processing') { %>` se cambia para que cuando `regenerateMode` sea true se entre al bloque MODO SSE en lugar de MODO LECTURA.
    - El `start-panel` muestra rama "¿Listo para regenerar?" con advertencia inline (texto + ícono naranja) y botón "Iniciar regeneración" cuando `regenerateMode`.
    - Función JS `initiateRegeneration()` agregada: hace `fetch PATCH ${CORE_API_URL}/api/v1/stories/${STORY_ID}/status { status: 'processing' }` y luego `startStream()`. En error, llama `showError(...)`.
    - Botón "Regenerar" del MODO LECTURA (`streaming-room.ejs:78-84`) se reemplaza por `<a href="/generar/stream/<%= storyId %>?regenerate=1">` (sin atributos `hx-*`).
  - Verify: navegar a `/generar/stream/:id?regenerate=1` con story `completed` → muestra pantalla regen; click "Iniciar regeneración" → DevTools Network muestra `PATCH .../status` con `processing` y luego `EventSource` activo; SQLite confirma `status=processing` y beats borrados.
  - Files: `frontend/src/controllers/stream.controller.ts`, `frontend/src/views/streaming-room.ejs`.

- [ ] **T3: Slice B — `generarDesdeHistoria` omite PATCH si status=completed**
  - Acceptance:
    - Antes del `axios.patch(... { status: 'processing' })`, el controller hace `axios.get(...)` para obtener el status actual.
    - Si `status === 'completed'`: skip PATCH, redirect a `/generar/stream/${storyId}?regenerate=1`.
    - Si `status === 'failed' | 'draft'`: comportamiento actual (PATCH + redirect a `/generar/stream/${storyId}` sin flag).
  - Verify: click "Regenerar" en galería sobre historia `completed` → DevTools muestra `GET /api/v1/stories/:id` y NO `PATCH .../status`; URL final `?regenerate=1`; SQLite: `status` sigue `completed`. Click "Reintentar" en `failed` → PATCH se dispara como antes.
  - Files: `frontend/src/controllers/historia.controller.ts`.

- [ ] **T4: Slice G — `historia.ejs` agrega `?regenerate=1` al link de regen**
  - Acceptance: en `historia.ejs:140`, cuando `story.status === 'completed'`, el `<a href="/generar/stream/<%= story.id %>">` se transforma en `<a href="/generar/stream/<%= story.id %>?regenerate=1">`.
  - Verify: visitar `/historia/:id` con `showStartButton=1` y status=completed → "Comenzar Regenerar" lleva a `?regenerate=1`.
  - Files: `frontend/src/views/historia.ejs`.

- [ ] **T5: Slice F — Limpieza de modal obsoleto**
  - Pre-acción: `grep -rn "modal_regenerar\|modalConfirmarRegenerar\|confirmar-regenerar" frontend/src frontend/tests` (R6) — confirmar que no hay tests dependientes.
  - Acceptance:
    - `frontend/src/views/partials/modal_regenerar.ejs` eliminado.
    - `modalConfirmarRegenerar` removido de `historia.controller.ts` (declaración + export).
    - Ruta `router.get("/modales/confirmar-regenerar/:storyId", ...)` removida de `routes/index.ts`.
    - Import de `modalConfirmarRegenerar` removido de `routes/index.ts`.
  - Verify: `grep -rn "modal_regenerar\|modalConfirmarRegenerar\|confirmar-regenerar" frontend/src` devuelve 0 hits. Build TypeScript del frontend pasa sin errores.
  - Files: `frontend/src/views/partials/modal_regenerar.ejs` (eliminado), `frontend/src/controllers/historia.controller.ts`, `frontend/src/routes/index.ts`.

- [ ] **T6: Verificación integral CA1-CA8**
  - Acceptance: los 8 criterios de aceptación del spec se cumplen en una pasada manual con stories en cada estado.
  - Verify:
    - **CA1:** click "Regenerar" en galería completed → URL `?regenerate=1`, SQLite `status=completed`.
    - **CA2:** sala con `?regenerate=1` muestra pantalla regen + advertencia; beats viejos siguen en DB.
    - **CA3:** click "Iniciar regeneración" → status=processing, beats borrados, SSE arranca.
    - **CA4:** cerrar pestaña en sala con `?regenerate=1` antes de click → status sigue completed, beats intactos.
    - **CA5:** "Ver avance" no aparece en galería para completed; sí para failed.
    - **CA6:** click "Regenerar" en sala MODO LECTURA → URL `?regenerate=1`, modal_regenerar no se abre.
    - **CA7:** grep confirma 0 hits a modal obsoleto en `frontend/src`.
    - **CA8:** "Reintentar" en story failed → flujo actual intacto (PATCH + SSE).
  - Files: ninguno (solo verificación).

---

## Plan técnico

### Componentes y dependencias

```
[Slice A] gallery.ejs         ── independiente
[Slice C] stream.controller.ts ┐
[Slice C] streaming-room.ejs   ├── acoplados (regenerateMode + UI MODO SSE)
[Slice D] streaming-room.ejs JS ┘   (mismo archivo que C)
[Slice E] streaming-room.ejs (MODO LECTURA botón) ── editar después de C+D estables
[Slice B] historia.controller.ts (generarDesdeHistoria) ── independiente, pero solo útil tras C
[Slice G] historia.ejs        ── independiente
[Slice F] limpieza modal obsoleto ── último (sin nada que dependa de modal_regenerar)
```

### Orden de implementación

1. **Slice A** — quick win, 1 línea cambiada en `gallery.ejs`.
2. **Slices C + D + E juntos** — mismo archivo `streaming-room.ejs` + controller `stream.controller.ts`. Toda la lógica de detección de query, pantalla de regen, JS `initiateRegeneration` y reemplazo del botón modal de MODO LECTURA en una sola pasada.
3. **Slice B** — `generarDesdeHistoria` consulta status y omite PATCH si `completed`.
4. **Slice G** — `historia.ejs` agrega `?regenerate=1` al link.
5. **Slice F** — limpieza de `modal_regenerar.ejs` + ruta + controller + import. Solo después de verificar que A-E-G funcionan, para no romper antes de tener el reemplazo activo.
6. **Verificación integral** — CA1-CA8 manual con stories en cada estado (`completed`, `failed`, `draft`).

### Verificaciones intermedias

- Tras Slice A: galería ya no muestra "Ver avance" para `completed`. Visual.
- Tras Slices C+D+E: `/generar/stream/:id?regenerate=1` con status=completed muestra pantalla regen. Click "Iniciar regeneración" hace PATCH desde JS y arranca SSE. DevTools Network.
- Tras Slice B: click "Regenerar" en galería NO patchea (status sigue completed). DevTools Network + query SQLite.
- Tras Slice G: "Comenzar Regenerar" en historia.ejs llega a sala con flag.
- Tras Slice F: `grep` confirma 0 hits a `modal_regenerar` / `confirmar-regenerar` en `frontend/src/`. El `dist/` se regenera con build.

### Análisis de riesgos (matizado)

| # | Riesgo | Probabilidad | Mitigación |
|---|---|---|---|
| **R1** | URL pegada `?regenerate=1` sin pasar por botón | Baja | Pantalla explica qué va a pasar; botón requiere acción |
| **R2** | F5 en sala con `?regenerate=1` antes de click → vuelve a MODO LECTURA | Baja | Aceptable: reentry sin daño (no destructivo) |
| **R3** | Race condition con dos pestañas | Muy baja | Aceptable, no es uso primario |
| **R4** | Latencia extra del `GET /api/v1/stories/:id` en controller B | Despreciable | ~1 query SQLite local |
| **R5** | Slice F borra archivos antes de que A-E estén estables → modal aparece roto si algo cae mid-flight | Baja | Slice F es el último (orden de implementación) |
| **R6** | Tests del frontend (si existen) referencian `confirmar-regenerar` | A relevar | `grep` previo en `frontend/tests/` antes de Slice F |
| **R7** | `streaming-room.ejs` no recibe `req` directamente — necesita que el controller le pase la flag | Confirmado | Slice C ya cubre: `stream.controller.ts` extrae `req.query.regenerate` y lo pasa al render context como `regenerateMode` |

### Reversibilidad

Cambios completamente reversibles. No hay migraciones de DB, no hay cambio de schema. El backend (Spec-216) no se toca, solo se invoca diferente. Si algo falla en producción, `git revert` de los 6 archivos modificados restaura el comportamiento previo. Único punto sin retorno trivial: Slice F borra `modal_regenerar.ejs` — pero está en git, recuperable con `git checkout HEAD~1`.

### Paralelización

Slices A y G son independientes y se podrían hacer en paralelo. En la práctica, el costo de coordinación supera el beneficio (ambos son cambios chicos en un archivo cada uno). Implementación serial recomendada para mantener tasks claras.
