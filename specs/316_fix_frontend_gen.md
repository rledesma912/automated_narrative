# Spec-316: Fix Frontend — scroll en relatos + acciones en `processing` + sidebar/footer en streaming-room

## Metadata

| Campo | Valor |
|-------|-------|
| **Status** | IMPLEMENT — D1.b + D2.a + D3.b + D4.a→c (2026-05-05) |
| **Tipo** | Bugfix UI/UX (frontend EJS + Tailwind) |
| **Slice base** | S0 |
| **Fecha** | 2026-05-05 |
| **Owner** | Frontend |
| **Specs relacionados** | 210 (web/streaming), 211 (footer global), 220 (wizard), 230 (ciclo de vida + modo monitor), 311 (galería + delete), 312 (persistencia automática) |

---

## 1. Objetivo

Resolver tres defectos UX que bloquean el cierre de la **release 1** (uso doméstico):

1. **Bug pequeño — Scroll ausente en vista de relatos.** El panel de relato en
   `relatos.ejs` no permite leer el texto completo cuando el contenido excede el
   viewport: queda truncado visualmente y el usuario no llega al final.
2. **Bug mediano — Card de galería sin acciones durante `processing`.** Cuando una
   historia está generándose, su card en `gallery.ejs` queda sin ningún CTA. El
   usuario no tiene cómo volver a la sala de streaming para ver el avance ni
   acceder a las acciones esperadas.
3. **Bug pequeño — Vista de relatos sin sidebar/footer.** Solo
   `/historia/:id/relatos` carece del chrome estándar (sidebar + footer),
   mientras que el resto de las páginas sí lo respetan. Causa raíz
   identificada en re-diagnóstico (ver §2.3).

---

## 2. Hallazgos confirmados

### 2.1 Bug 1 — `relatos.ejs` sin scroll efectivo

- Layout base (`frontend/src/views/partials/layout.ejs:61-67`):
  ```html
  <body class="flex h-screen overflow-hidden ...">
    <main class="flex-1 overflow-y-auto p-12 pb-24">
      <%- body %>
    </main>
  ```
  → `<main>` provee scroll vertical y un `pb-24` para no chocar con el footer.

- Footer global fijo (`frontend/src/views/partials/footer.ejs:1-3`):
  ```html
  <div id="global-status-footer"
       class="fixed bottom-0 left-56 right-0 ... h-10 ...">
  ```
  → Tapa los últimos 40px del viewport.

- Vista de relatos (`frontend/src/views/relatos.ejs:46-63`):
  ```html
  <section class="relato-panel border border-forge-border bg-forge-surface p-8 ...">
    ...
    <div id="relato-content-..." class="prose ... whitespace-pre-wrap ... text-base">
      <%= relato.content %>
    </div>
  </section>
  ```
  → No hay `max-h` ni `overflow-y` en el panel ni en el contenedor de prose.

**Síntoma reportado por el usuario:** el relato se ve truncado y no se accede al
final. Causa probable: el `<main>` sí scrollea, pero (a) el footer fijo + el
ancho del scrollbar custom hacen que los últimos párrafos queden visualmente
"cortados" en pantallas chicas, y (b) el `prose` tiene `max-w-none` y crece sin
límite vertical, lo que en algunos zoom levels hace que el footer pise el final
del texto incluso con `pb-24`.

> **Hipótesis a confirmar en navegador:** reproducir en viewport 1366×768 y en
> zoom 110%. Si el `<main>` scrollea hasta el final del contenido, el problema
> se reduce a ajustar el padding inferior. Si el contenido no llega a verse,
> hay que dar scroll interno al panel.

### 2.2 Bug 2 — Card de galería sin acciones durante `processing`

`frontend/src/views/gallery.ejs:46-92`:

```ejs
<div class="flex items-center gap-6 flex-wrap">
  <% if (s.status !== 'processing') { %>
    <a href="/generar/cargar/...">Editar</a>
    <% if (s.status === 'completed') { %>
      <form .../generar>Regenerar</form>
    <% } else { %>
      <form .../generar>Generar / Reintentar</form>
    <% } %>
    <a href="/historia/.../relatos">Ver Relato</a>
    <button hx-get=".../confirmar-borrar/...">Eliminar</button>
  <% } %>

  <% if (s.status === 'failed') { %>
    <a href="/generar/stream/...">Ver avance</a>
  <% } %>
</div>
```

→ Cuando `s.status === 'processing'`:
- Las cuatro acciones principales (`Editar`, `Regenerar/Generar`, `Ver Relato`,
  `Eliminar`) quedan ocultas por la condición `s.status !== 'processing'`.
- El bloque secundario (`Ver avance`) sólo se muestra si `failed`, no si
  `processing`.
- **Resultado:** la card no tiene ningún botón.

**Backend ya soporta el caso (Spec-210/230):**
- `GET /generar/stream/:storyId` con `monitorMode = (storyStatus === 'processing' && !regenerateMode)`
  (`frontend/src/controllers/stream.controller.ts:74`) — re-conecta el SSE a la
  sesión activa via `StreamSessionManager`, sin disparar otra generación.
- El footer global (`partials/footer.ejs`) ya muestra "Ver progreso" cuando hay
  stream activo, pero requiere que el usuario lea ahí abajo. La galería debería
  ser autoexplicativa.

### 2.3 Bug 3 — Vista de relatos sin sidebar/footer (causa raíz identificada)

**Re-diagnóstico (2026-05-05):** el usuario confirmó que **todas** las páginas
muestran sidebar+footer **excepto `/historia/:id/relatos`**. Esto invalida la
hipótesis inicial (que apuntaba a `streaming-room.ejs`) y cambia la causa raíz.

**Causa raíz real:**

`frontend/src/controllers/relatos.controller.ts:19` invoca
`res.render("relatos", { ... })` directamente — **sin pasar por `renderPage()`**.
Como `renderPage` es la función que envuelve la vista en `partials/layout.ejs`
(que es donde se incluyen `sidebar` y `footer`), la vista de relatos se renderiza
"desnuda" y solo retorna el HTML interno de `relatos.ejs`.

Comparativa con todos los otros controllers del frontend (todos usan `renderPage`):
- `gallery.controller.ts:25` → `await renderPage(res, "gallery", ...)`
- `historia.controller.ts:18` → `await renderPage(res, "historia", ...)`
- `stream.controller.ts:87` → `await renderPage(res, "streaming-room", ...)`
- `debug.controller.ts:14` → `await renderPage(res, "debug", ...)`
- `generate.controller.ts:5` → `await renderPage(res, "generate", ...)`
- `theme.controller.ts` → `renderPage(...)`
- **`relatos.controller.ts:19` → `res.render("relatos", ...)` ← anomalía única**

**Fix:** cambiar `res.render("relatos", ...)` por
`await renderPage(res, "relatos", ...)`. Una línea + un import.

**Nota sobre `streaming-room.ejs`:** el cambio de `max-w-5xl` → `max-w-4xl`
aplicado en S3-T2 (D4.c) sigue siendo válido como mejora de consistencia
visual con las otras vistas; no era el fix del bug pero tampoco lo daña.

### 2.4 Comportamiento esperado del usuario

- Estando una historia en `processing`, el usuario quiere **un CTA visible en la
  card** que lo lleve a la sala de generación para ver el avance en vivo.
- Adicionalmente quiere disponer de los botones que normalmente vería
  (especialmente "Ver Relato" y la acción de regeneración) — interpretación
  literal: ambos como atajos a la sala de streaming.

---

## 3. Decisiones de producto pendientes

### D1 — Estrategia de scroll en `relatos.ejs`

- **D1.a (mínima)**: confirmar que el `<main>` ya scrollea y aumentar el
  `pb-` de `relatos.ejs` para que el último párrafo nunca quede tapado por el
  footer fijo. **Ventaja**: 1 línea de cambio, scroll del documento entero.
  **Desventaja**: no responde a la solicitud literal de "agregar scroll a la vista".

- **D1.b (recomendada)**: dar scroll **interno** al panel del relato con
  `max-h: calc(100vh - <margen>)` + `overflow-y-auto`. **Ventaja**: el header
  ("Volver a Galería" + título + tabs de variantes) queda fijo arriba mientras
  el lector navega el cuerpo del relato. **Desventaja**: requiere calcular bien
  el `max-h` para no romper en mobile.

- **D1.c**: combinar — el panel scrollea internamente Y mantener un `pb-32` en
  `<main>` como red de seguridad. Más robusto pero más cambios.

### D2 — Composición de la card cuando `status === 'processing'`

- **D2.a (recomendada)**: un único CTA primario **"Ver avance"** (link a
  `/generar/stream/:id`) + `Eliminar` con confirmación HTMX. Sin `Editar`
  (la historia ya se está generando) ni `Regenerar` (redundante: ya hay una
  corrida en curso).

- **D2.b (literal del pedido)**: dos CTAs visibles ("Ver Relato" + "Regenerar")
  ambos apuntando a `/generar/stream/:id`. Visualmente igual a otros estados
  pero con destino unificado. **Riesgo**: confuso — dos labels distintos para
  la misma acción.

- **D2.c (intermedia)**: mostrar **"Ver avance"** como CTA destacado +
  `Eliminar`, y al pasar a `completed` reaparecen los CTAs estándar (Editar,
  Regenerar, Ver Relato, Eliminar). Es D2.a etiquetada explícitamente.

### D4 — Estrategia de fix para sidebar/footer en `relatos.ejs`

Tras el re-diagnóstico (§2.3), la decisión es **D4 único**: portar
`relatos.controller.ts` al patrón `renderPage()` que ya usan todos los demás
controllers. Cambio mínimo, simétrico, sin tocar la vista ni el layout.

> **Aplicado**: `frontend/src/controllers/relatos.controller.ts` ahora invoca
> `await renderPage(res, "relatos", ...)`. Test unitario actualizado para
> verificar el contrato nuevo (la vista se renderiza vía layout y los locals
> se propagan al wrapper).

### D3 — `Eliminar` durante `processing`

- **D3.a**: permitirlo con confirmación reforzada ("Esto cancelará la
  generación en curso"). Requiere que el backend cancele la sesión SSE activa
  (verificar que `DELETE /api/v1/stories/{id}` ya lo hace o agregar limpieza).
- **D3.b**: deshabilitarlo durante `processing` (CTAs neutralizados). Más
  conservador, evita estados inconsistentes.

> **Recomendación combinada**: D1.b + D2.a + D3.b + D4.a → D4.c.
> Solución mínima y sin sorpresas para el usuario doméstico.

---

## 4. Diseño propuesto (asumiendo D1.b + D2.a + D3.b)

### 4.1 `relatos.ejs` — scroll interno del panel

```ejs
<section
  id="relato-panel-..."
  class="relato-panel border border-forge-border bg-forge-surface p-8
         max-h-[calc(100vh-16rem)] overflow-y-auto ..."
>
  ...
</section>
```

- `max-h-[calc(100vh-16rem)]` deja ~16rem para header + tabs + footer.
- `overflow-y-auto` activa scroll interno cuando el relato lo excede.
- Mantener `pb-24` del `<main>` para coherencia con otras vistas.

### 4.2 `gallery.ejs` — acciones por estado

Extraer la condicional grande a un patrón claro:

```ejs
<div class="flex items-center gap-6 flex-wrap">
  <% if (s.status === 'processing') { %>
    <a href="/generar/stream/<%= s.id %>"
       class="text-sm text-forge-accent hover:opacity-70 flex items-center gap-2">
      <i data-lucide="eye" class="w-4 h-4"></i> Ver avance
    </a>
    <%/* Eliminar desactivado durante processing — D3.b */%>
    <span class="text-xs text-forge-muted italic">
      Generación en curso...
    </span>
  <% } else { %>
    <a href="/generar/cargar/<%= s.id %>">Editar</a>
    <% if (s.status === 'completed') { %>
      <form .../generar>Regenerar</form>
      <a .../relatos>Ver Relato</a>
    <% } else if (s.status === 'failed') { %>
      <form .../generar>Reintentar</form>
      <a .../stream>Ver avance</a>
    <% } else { /* draft */ %>
      <form .../generar>Generar</form>
    <% } %>
    <button hx-get=".../confirmar-borrar/<%= s.id %>">Eliminar</button>
  <% } %>
</div>
```

- Card `processing` queda con un único CTA claro + microcopy de estado.
- `failed` mantiene "Ver avance" como hoy.
- `completed` y `draft` no cambian.
- "Ver Relato" sólo aparece si `completed` (alineado con que `generated_narrative`
  recién existe tras el éxito de Spec-312).

### 4.3 `relatos.ejs` — restaurar chrome estándar (causa raíz)

`relatos.controller.ts`:
```ts
import { renderPage } from "../utils/render";
// ...
await renderPage(res, "relatos", {
  story,
  relatos,
  title: `Relatos de "${story.title || 'Sin título'}"`,
  activePage: "gallery",
});
```

Resultado: la vista pasa por `partials/layout.ejs` igual que el resto, y
sidebar+footer aparecen automáticamente.

Como bonus, `streaming-room.ejs` también se alineó visualmente cambiando el
wrapper raíz del MODO SSE de `max-w-5xl` → `max-w-4xl` para consistencia con
`gallery.ejs` y los modos monitor/lectura del propio archivo.

### 4.4 No tocar

- `partials/layout.ejs` (a menos que D4.c lo requiera).
- `partials/sidebar.ejs` (no hay regresión reportada en otras páginas).
- `partials/footer.ejs` (idem).
- `stream.controller.ts` (lógica de monitor/regenerate ya está).
- Backend: nada cambia.

---

## 5. Scope

### In Scope
- Cambios CSS/HTML en `relatos.ejs` para scroll interno del panel.
- Refactor de la condicional de acciones en `gallery.ejs`.
- Tests de frontend (vitest) que verifiquen el árbol de CTAs por estado.
- Smoke manual en navegador (galería con historia en `processing` + lectura
  completa de un relato largo).

### Out of Scope
- Cambios en backend / endpoints.
- Cambios visuales fuera de los 2 archivos `.ejs`.
- Cancelación efectiva de la sesión SSE al borrar (queda para spec posterior si
  se elige D3.a).
- Rediseño del footer global o del modo monitor.

---

## 6. Slices propuestos (esqueleto — TASKS pendiente de OK)

### Slice S0 — Reproducción
- S0-T1: reproducir Bug 1 abriendo un relato largo en navegador, capturar
  comportamiento actual.
- S0-T2: reproducir Bug 2 forzando una historia en `processing` (puede ser
  iniciar una generación SSE y refrescar `/galeria` durante el proceso).
- S0-T3: snapshot `cd frontend && npm test` (referencia 15 passed).
- S0-T4: reproducir Bug 3 navegando a `/generar/stream/<id>` en cada modo
  (monitor/SSE/lectura) y confirmar visualmente si sidebar/footer aparecen.
  Identificar causa raíz (C1/C2/C3/C4 de §2.3).

### Slice S1 — Fix scroll en relatos
- S1-T1: aplicar `max-h-[calc(100vh-16rem)] overflow-y-auto` a cada
  `.relato-panel` en `relatos.ejs`.
- S1-T2: validar manualmente con relato de >2000 palabras que el scroll
  funciona y los tabs siguen accesibles.
- S1-T3: ajustar `max-h` si en pantallas comunes (1366×768, 1920×1080) el
  panel queda demasiado corto o demasiado largo.

### Slice S2 — Acciones de card en `processing`
- S2-T1: refactorizar el bloque de acciones de `gallery.ejs` siguiendo §4.2.
- S2-T2: agregar microcopy "Generación en curso..." debajo de "Ver avance".
- S2-T3: si se confirma D3.b, omitir el botón Eliminar durante `processing`;
  si D3.a, mantenerlo con texto de confirmación reforzado en el modal.

### Slice S3 — Restaurar chrome en `relatos.ejs` (re-diagnóstico)
- S3-T1: portar `relatos.controller.ts` a `renderPage()` (causa raíz real).
- S3-T2: actualizar `tests/unit/controllers/relatos.controller.test.ts` para
  reflejar el contrato nuevo (`view === "partials/layout"`, locals propagados,
  `body` string).
- S3-T3 (bonus): alinear wrapper del MODO SSE de `streaming-room.ejs` de
  `max-w-5xl` a `max-w-4xl` por consistencia visual con `gallery.ejs`.

### Slice S4 — Tests + validación final
- S4-T1: test vitest que renderice `gallery.ejs` con stories en cada estado
  (`draft`, `processing`, `completed`, `failed`) y verifique los CTAs presentes.
- S4-T2: smoke manual del flujo: iniciar generación SSE, abrir galería en otra
  pestaña, hacer click en "Ver avance" → debe abrir la sala en modo monitor
  con sidebar+footer visibles.
- S4-T3: verificar que tras `completed` los CTAs vuelven a ser los habituales
  (Editar, Regenerar, Ver Relato, Eliminar).
- S4-T4: `cd frontend && npm test` + `make lint` + `make test` verdes.

---

## 7. Criterios de aceptación

1. En `/historia/:id/relatos` con relato largo (>2000 palabras), el usuario
   puede leer hasta el último párrafo (scroll funcional, sin truncamiento por
   footer).
2. Los tabs de variantes y el botón "Volver a Galería" siguen visibles mientras
   se scrollea el cuerpo del relato (si se elige D1.b).
3. En `/galeria`, una card con `status='processing'` muestra al menos un CTA
   visible que lleva a `/generar/stream/:id`.
4. Esa CTA, al hacer click, abre la sala en **modo monitor** (sin disparar una
   nueva generación, según Spec-230).
5. Cards en estados `draft`, `completed`, `failed` mantienen el mismo set de
   CTAs que tenían antes del cambio (sin regresión).
6. En `/historia/:id/relatos`, el sidebar izquierdo y el footer global son
   visibles igual que en `/galeria` y el resto de las páginas.
7. `cd frontend && npm test` pasa (mantener o aumentar contador, baseline 15).
8. `make lint` y `make test` siguen verdes.

---

## 8. Riesgos

- **Cálculo de `max-h` en mobile**: viewports muy bajos pueden volver el panel
  inutilizable. Validar en al menos 1366×768 y 1920×1080; mobile queda fuera de
  scope para release 1 (uso doméstico desktop).
- **D3.b deja sin Eliminar a historias atascadas en `processing`**: si una
  generación queda colgada (por ejemplo Ollama caído), el usuario no puede
  borrar la card desde galería. Mitigación: el endpoint `DELETE` sigue
  disponible vía API; podría exponerse desde la pantalla de detalle de
  historia, pero no es bloqueante para release 1.
- **HTMX boost en `<a>`**: el body usa `hx-boost="true"`. Verificar que el link
  "Ver avance" no rompe el SSE al hacer swap parcial (probablemente sí porque
  cambia URL completa, pero confirmar en S3-T2).
- **Test snapshot de EJS**: si los tests del frontend hacen snapshot del HTML
  renderizado, este cambio de gallery los rompe → actualizar baselines.

---

## 9. Notas

- Ya existen patrones similares en el código:
  - "Ver avance" para `failed` (`gallery.ejs:86-91`) — reusar literalmente.
  - Modo monitor en streaming-room (`stream.controller.ts:74`) — el destino
    funciona out-of-the-box.
- Microcopy "Generación en curso..." es coherente con la etiqueta de estado
  ("Generando") definida en `gallery.ejs:7` (`renderStatusLabel`).

---

## 10. Estado

- [x] SPECIFY — hallazgos confirmados con archivos y líneas.
- [x] PLAN — D1.b + D2.a + D3.b + D4.a→c aprobados (2026-05-05).
- [x] TASKS — slices S0–S4 expandidos.
- [x] IMPLEMENT — completado (2026-05-05).

## 11. Resultado de implementación (2026-05-05)

**Cambios aplicados:**

- `frontend/src/views/relatos.ejs` — agregado `max-h-[calc(100vh-16rem)]
  overflow-y-auto` al `<section class="relato-panel">` (D1.b). Cada relato
  scrollea internamente; el header (Volver + título + tabs) queda fijo.
- `frontend/src/views/gallery.ejs` — refactor del bloque de acciones (D2.a +
  D3.b):
  - `processing` → un único CTA "Ver avance" + microcopy "Generación en curso..."
    (sin Editar/Regenerar/Eliminar).
  - `completed` → Editar + Regenerar + Ver Relato + Eliminar.
  - `failed` → Editar + Reintentar + Ver avance + Eliminar.
  - `draft` → Editar + Generar + Eliminar.
- `frontend/src/views/streaming-room.ejs` — wrapper raíz del MODO SSE alineado
  de `max-w-5xl` a `max-w-4xl` por consistencia visual con `gallery.ejs` y los
  otros modos del propio archivo (bonus, no era el bug real).
- `frontend/src/controllers/relatos.controller.ts` — portado de
  `res.render("relatos", ...)` a `await renderPage(res, "relatos", ...)`. Causa
  raíz real del Bug 3: era el único controller que no usaba `renderPage`, por
  eso solo `relatos.ejs` se renderizaba sin chrome.
- `frontend/tests/unit/controllers/relatos.controller.test.ts` — actualizado
  para verificar el contrato nuevo (`view === "partials/layout"`, locals
  propagados al wrapper, presencia de `body` como string).

**Verificación:**

- Backend: `ruff check .` → All checks passed; `pytest tests` → **509 passed**.
- Frontend: `npm test` → **37 passed / 2 failed** (los 2 fallos son
  pre-existentes en `tests/integration/css-architecture/`, ajenos al spec —
  faltan archivos generados por `npm run build:css`).
- Smoke manual para release 1:
  1. `/galeria` con historia en `processing` → ver CTA "Ver avance".
  2. Click → sala en modo monitor con sidebar/footer visibles.
  3. `/historia/:id/relatos` → sidebar y footer presentes; relato largo
     scrollea internamente sin que el final quede tapado.
