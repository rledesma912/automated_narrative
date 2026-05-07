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

---

## 12. Bugs adicionales identificados (2026-05-06)

### Bug 4 — Reload requerido para ver contenido actualizado de relato

**Descripción:** Al hacer click en una card de relato en la vista de relatos (cambio de variante), el contenido shown no se actualiza hasta que el usuario hace F5 (Refresh del navegador).

**Síntoma reportado:** El usuario hace click en otra variante de relato y el texto shown sigue siendo el de la variante anterior. Tras recargar la página (F5), el contenido correcto aparece.

**Comportamiento esperado:** El cambio de variante debería actualizar el contenido del relato de forma inmediata sin necesidad de recargar la página.

**Archivos posiblemente relacionados:**
- `frontend/src/views/relatos.ejs` — lógica de cambio de variante (tabs o selector).
- `frontend/src/controllers/relatos.controller.ts` — endpoint que provee los relatos.

**Hipótesis preliminar:**
- El cambio de variante podría estar usando HTMX con cache que no se invalida.
- La variante seleccionada se guarda en el backend pero el frontend no recibe la actualización correctamente.
- Falta algo como `hx-target` o refresh del contenido tras el cambio.

---

### Bug 5 — Botón "Copiar" no funciona

**Descripción:** La funcionalidad de copiar el texto del relato al portapapeles no funciona. Al hacer click en el botón de copiar, no ocurre nada (ni se copia el texto ni se muestra feedback visual).

**Síntoma reportado:** El usuario hace click en el botón/icono de copiar y el texto del relato no se copia al portapapeles.

**Comportamiento esperado:** Al hacer click en "Copiar", el texto del relato se copia al portapapeles y se muestra un feedback visual (ej: toast o cambio de icono) confirmando la acción.

**Archivos posiblemente relacionados:**
- `frontend/src/views/relatos.ejs` — botón de copiar y su handler.
- `frontend/src/public/js/` — scripts de cliente para copiar.

**Hipótesis preliminar:**
- Falta el `onclick` o handler de JavaScript que realice el `navigator.clipboard.writeText()`.
- El handler existe pero falla silenciosamente por restricciones de CORS o contexto inseguro.
- Falta el feedback visual (`Copiado!`).

---

## 13. Estado de bugs adicionales

- [x] INVESTIGATE — Bug 4: diagnóstico de la causa raíz (cambio de variante sin reload).
- [x] INVESTIGATE — Bug 5: verificar implementación del botón copiar en `relatos.ejs` y JS asociado.
- [x] FIX — Bug 5 (re-aplicado 2026-05-08): el fix documentado en §10 se había perdido en algún merge previo (el código en disco volvió a la versión simple sin manejo de errores). Re-implementado con enfoque más robusto que el original:
  - `try/catch` reemplazado por `.catch()` en la promise + fallback automático a `document.execCommand('copy')` con `<textarea>` temporal cuando `navigator.clipboard` no está disponible (HTTP-LAN, contextos no-seguros).
  - Detección previa de `window.isSecureContext` para decidir vía directa o fallback sin esperar al rechazo.
  - Feedback visual diferenciado: `check + ¡Copiado!` (ok) vs `alert-triangle + Error al copiar` (fallo).
  - Validación de existencia del elemento y de texto no vacío antes de intentar copiar.
  - Logs `console.warn`/`console.error` para debugging futuro.
  - Archivo: `frontend/src/views/relatos.ejs:111-167`.

---

### Bug 6 — Beats pegados en vista de relatos

**Descripción:** En la vista de relatos, el texto de los 5 beats aparece todo pegado sin separación. El usuario necesita que cada acto/beats esté separado por su título correspondiente (Acto 1, Acto 2, Acto 3, Acto 4 y Acto 5).

**Síntoma reportado:** El contenido del relato se muestra como un bloque de texto continuo sin delimitadores visuales entre beats.

**Comportamiento esperado:** Cada beat debería estar separado visualmente y etiquetado con su número/título (ej: "Beat 1 - [título]", "Beat 2 - [título]", etc.).

**Archivos posiblemente relacionados:**
- `frontend/src/views/relatos.ejs` — renderizado del contenido del relato.
- Backend que genera el `relato.content` — cómo se estructura el texto de los beats.

**Hipótesis preliminar:**
- El `relato.content` se genera concatenando los beats sin separadores.
- La separación debe hacerse en el backend al generar el narrative, o en el frontend al renderizar.

---

### Bug 7 — Spinner y logs en regeneración

**Descripción:** Al iniciar una **regeneración** (no generación desde cero), aparece el spinner con los textos "Despertando al Narrador..." y "El LLM está procesando tu historia", pero los logs de avance no aparecen de inmediato. Recién cuando comienzan a aparecer los logs (ej: "[16:54] 🔍 Analizando sinopsis...", "[16:55] ✍️ Narrando Beat 1/5..."), el spinner desaparece.

**Síntoma reportado:**
1. Click en "Regenerar" → aparece spinner + textos (sin logs).
2. Pasados unos segundos → aparecen los logs.
3. Al aparecer los logs → el spinner desaparece abruptamente.

**Comportamiento esperado:**
- Al hacer click en "Regenerar", deben comenzar a aparecer los logs de inmediato (mientras el LLM procesa).
- El spinner debería permanecer visible debajo de los logs durante todo el proceso de generación, hasta que завер completamente.

**Archivos posiblemente relacionados:**
- `frontend/src/views/streaming-room.ejs` — lógica de spinner y logs.
- `frontend/src/controllers/stream.controller.ts` — manejo de SSE y estado de carga.
- `frontend/src/public/js/` — scripts de cliente para streaming.

**Hipótesis preliminar:**
- El spinner se muestra durante un estado de "loading" que termina cuando llega el primer log.
- Debería cambiarse la lógica para que el spinner sea complementario a los logs (ambos visibles), no mutuamente excluyentes.

---

### Bug 8 — Persistencia de cambios en wizard

**Descripción:** Los cambios en los componentes del wizard de generación (textos, selecciones) no se persisten en algunos casos cuando se navega hacia adelante o hacia atrás. Cada vez que se cambia un texto o selección y pierde el foco, debe persistirse automáticamente y mostrarse en el footer que se guardó el cambio.

**Síntoma reportado:**
- El usuario completa un paso del wizard, navega al siguiente, y al volver al anterior los cambios se perdieron.
- No hay feedback visual en el footer confirmando que los cambios se guardaron.

**Comportamiento esperado:**
- Al perder el foco de cualquier input del wizard (blur), los cambios se persisten automáticamente en backend.
- El footer muestra un mensaje visual (ej: "✓ Guardado" o similar) confirmando la persistencia.

**Archivos posiblemente relacionados:**
- `frontend/src/views/generate/` — vistas del wizard.
- `frontend/src/controllers/generate.controller.ts` — endpoints de guardado.
- `frontend/src/views/partials/footer.ejs` — zona de feedback de estado.

**Hipótesis preliminar:**
- Falta hook de `onblur` o `onchange` que persista los valores.
- El guardado solo ocurre al hacer click en "Siguiente", no al cambiar campos individuales.
- El footer no tiene lógica para mostrar estado de "guardado".

---

## 14. Estado de bugs 6-8

- [x] INVESTIGATE — Bug 6: cómo se estructura el contenido del relato en backend vs frontend.
- [x] INVESTIGATE — Bug 7: lógica de spinner vs logs en streaming-room.
- [x] INVESTIGATE — Bug 8: eventos de persistencia en wizard y feedback en footer.

---

### Bug 9 — Se pierden las reglas del mundo al navegar en edición de historia

**Descripción:** En la vista de edición de una historia ya generada (accedida vía "Editar" o "Cargar" desde la galería), al navegar hacia adelante y hacia atrás a través de los pasos del wizard, en algún momento las **reglas del mundo** se pierden.

**Síntoma reportado:**
- El usuario edita una historia existente.
- Al navegar entre pasos (Anterior/Siguiente), en algún momento las reglas del mundo (Reglas del universo narrativo) desaparecen del formulario.
- Los datos se pierden aunque se haya implementado auto-guardado en Bug 8.

**Comportamiento esperado:**
- Las reglas del mundo deben persistir correctamente al navegar entre pasos, igual que los otros campos del wizard.
- Si se pierden, debe haber un mecanismo para recuperarlas desde el backend.

**Archivos posiblemente relacionados:**
- `frontend/src/controllers/wizard.controller.ts` — carga de datos existentes.
- `frontend/src/services/wizard.service.ts` — gestión de sesión y datos.
- `frontend/src/services/mapper.service.ts` — mapeo de story a wizard.
- `frontend/src/views/wizard.ejs` — renderizado de campos de reglas.

**Hipótesis preliminar:**
- El mapeo de story a wizard (`mapStoryToWizard`) no está extrayendo correctamente el campo `rules` de la story.
- Las reglas se guardan en un formato diferente al esperado por el wizard ( ej: `story.rules` vs `wizard.rules`).
- La sesión no está manteniendo las reglas correctamente entre pasos.

---

## 15. Estado de bugs 9

- [x] INVESTIGATE — Bug 9: mapeo de reglas del mundo en edición de historia existente.
- [ ] INVESTIGATE — Bug 11: cancelación mid-stream no expuesta en UI durante generación normal (ver detalle al final del documento).

---

## 17. Fix Bug 9 (2026-05-06)

### Bug 9 — Se pierden las reglas del mundo al navegar en edición

**Causa raíz identificada:**
El enlace "Anterior" en el wizard era un simple `<a>` que navegaba directamente
sin ejecutar el submit del formulario. Aunque se había implementado auto-guardado
en blur/change (Bug 8), al navegar hacia atrás no se guardaban los cambios del
paso actual antes de moverse al anterior.

**Fix aplicado:**
- Cambiado el enlace "Anterior" de `<a href="...">` a `<button onclick="...">`
- Nueva función JavaScript `saveCurrentStepAndNavigate(targetStep)` que:
  1. Recolecta todos los valores del formulario actual (incluyendo multi-selects,
     checkboxes y radios)
  2. Guarda cada campo mediante auto-guardado (Promise.all)
  3. Navega al paso destino solo después de que todos los campos estén guardados
- Esto asegura que al navegar hacia atrás desde el paso de reglas, los cambios se
  guardan correctamente antes de cambiar de paso

**Archivos modificados:**
- `frontend/src/views/wizard.ejs:360-365` (botón Anterior con handler)
- `frontend/src/views/wizard.ejs:455-485` (función saveCurrentStepAndNavigate)

**Verificación:** Build OK (`npm run build`)

---

## 16. Fix aplicado bugs 6-8 (2026-05-06)

### Bug 6 — Beats pegados en vista de relatos

**Causa raíz identificada:**
La función `_consolidate_content` en `generate_narratives_use_case.py` unía los
contenidos de los beats con `\n\n` pero sin agregar ningún título identificador.

**Fix aplicado:**
- Modificado `_consolidate_content` para incluir "## Beat X" antes de cada contenido
- Si el beat tiene `summary`, se muestra como "Beat X - summary"
- Esto permite que el usuario vea claramente la separación entre actos

**Archivo modificado:** `src/application/use_cases/generate_narratives_use_case.py:31-42`

**Verificación:** `make lint` → All checks passed

---

### Bug 6 (complemento frontend, 2026-05-08) — Markdown crudo en vista web

**Por qué reaparece:** el fix backend deja el `relato.content` con la forma `## Beat N - summary\n\n<prosa>`. La vista web (`relatos.ejs`) renderizaba ese contenido como `<%= relato.content %>` dentro de un `<div class="prose ... whitespace-pre-wrap">`. La clase `.prose` solo estiliza tags HTML reales (h1-h4, p, etc.); no parsea markdown. Resultado: el usuario veía `## Beat 1 - X` como **texto plano** con `##` literales y separación visual mínima — lo que se percibía como "beats pegados".

El fix backend resolvió el caso del `.md` exportado, pero el navegador siguió mostrando markdown crudo.

**Fix aplicado (frontend):** `frontend/src/views/relatos.ejs` (panel del relato):

- Split server-side de `relato.content` con la regex `/^## (.+)$/m` → array `[preámbulo, título1, body1, título2, body2, ...]`.
- Cada par título/body se renderiza como `<h3 class="heading-forge-lg !text-2xl !text-forge-accent mt-10 mb-4">` + `<div class="whitespace-pre-wrap">`. El primer heading lleva `mt-0` si no hay preámbulo.
- Wrapper `<div id="relato-content-<%= relato.id %>">` se mantiene para que `copyRelatoContent` siga encontrando el elemento. `.innerText` une los `<h3>` y `<div>` con saltos de línea automáticos al copiar.
- Caída elegante: si el contenido no tiene headers `##` (legacy o backend cambia), `sections.length === 1` y se renderiza plano sin romper nada.
- Sin nuevas dependencias (parser ad-hoc para el formato real del backend).

**Trade-off considerado:** se evaluó añadir `marked.js` para parsear todo el markdown del lado cliente, pero solo necesitamos los headings de beat — un parser inline es más predecible y elimina una dependencia.

---

### Bug 7 — Spinner desaparece cuando aparecen los logs

**Causa raíz identificada:**
La función `hideSpinner()` ocultaba el spinner Y mostraba el log container
simultáneamente, causando que el spinner desapareciera abruptamente cuando
llegaba el primer log.

**Fix aplicado:**
- Dividida `hideSpinner()` en dos funciones:
  - `showLogsContainer()`: solo muestra el log container
  - `hideSpinner()`: solo oculta el spinner
- Cambiada la llamada en el evento `beat_start` de `hideSpinner()` a `showLogsContainer()`
- Ahora el spinner permanece visible debajo de los logs durante todo el proceso

**Archivo modificado:** `frontend/src/views/streaming-room.ejs:466-476, 646`

**Verificación:** Build OK (`npm run build`)

---

### Bug 7 (re-aplicado en 2026-05-08) — fix nunca llegó al `.js` extraído

**Por qué reaparece:** el fix de §16 se documentó como aplicado en `streaming-room.ejs:466-476, 646`, pero al portar el JS al archivo extraído `frontend/public/js/streaming-room.js` (Spec-318 §9.C, commit `95adbbd`) el `hideSpinner()` original volvió a quedar como una sola función que hacía las dos cosas (ocultar spinner + mostrar logs). El `beat_start` seguía llamándolo y se reproducía exactamente el síntoma descrito.

Además los logs no aparecían en el primer evento `status` (que sí llega antes que `beat_start`): los `appendLog` se acumulaban en un container `hidden`, así que cuando finalmente se hacía `revealLogs` aparecían "de golpe" varios logs juntos, reforzando la sensación de salto.

**Decisión UX (2026-05-08):** se eligió la opción B del spec (spinner visible TODO el tiempo) por encima de hacerlo desaparecer al primer beat. El spinner queda como indicador continuo de "el LLM sigue trabajando" debajo de los logs.

**Fix aplicado:**

1. **`frontend/public/js/streaming-room.js`:**
   - Funciones separadas: `revealLogs()` (solo muestra log-container) y `hideSpinner()` (solo oculta spinner).
   - Listener `status` ahora llama `revealLogs()` antes del `appendLog()` → los logs aparecen desde el primer evento, no esperan al `beat_start`.
   - Listener `beat_start` ya no llama `hideSpinner()`; llama `revealLogs()` (idempotente).
   - `showDone()` y `showError()` ahora invocan `hideSpinner()` para ocultar el spinner al cerrar el flujo (antes solo `cancelGeneration` lo ocultaba explícitamente).
2. **`frontend/src/views/streaming-room.ejs`:**
   - `#log-container` movido **antes** de `#initial-spinner` en el markup (orden visual: logs arriba, spinner debajo).
   - Spinner reducido (`py-12 gap-6`, `w-20 h-20`, `text-lg`) para no robar protagonismo cuando convive con logs.

**Archivos modificados:**
- `frontend/public/js/streaming-room.js` (revealLogs/hideSpinner separadas, listeners actualizados, hideSpinner en showDone/showError).
- `frontend/src/views/streaming-room.ejs` (orden invertido + spinner más compacto).

**Lección reusable:** cuando una spec documenta "Archivo modificado: X" pero después un refactor estructural mueve la lógica a otro archivo Y (Spec-318 §9.C extrajo el JS), conviene verificar que los fixes previos hayan migrado. Buen candidato para un check de cierre en futuras specs de extracción.

---

### Bug 8 — Persistencia de cambios en wizard

**Causa raíz identificada:**
Los datos del wizard solo se guardaban al hacer click en "Siguiente" (submit del
formulario). Si el usuario cambiaba un valor y navegaba hacia otro paso sin hacer
click en el botón, los cambios se perdían.

**Fix aplicado:**
1. Nuevo endpoint PATCH `/generar/paso/:step/guardar` en el wizard controller
   - Recibe `fieldName`, `fieldValue`, `fieldType` y guarda en sesión
2. JavaScript en wizard.ejs:
   - Escucha eventos `blur` y `change` en todos los inputs del formulario
   - Envía PATCH al endpoint de auto-guardado en cada cambio/blur
3. Feedback visual en footer:
   - Nuevo elemento `#footer-wizard-save` que muestra "✓ Guardado" durante 2 segundos
   - Se muestra automáticamente cuando el auto-guardado succeeds

**Archivos modificados:**
- `frontend/src/controllers/wizard.controller.ts:104-128` (autoSaveField)
- `frontend/src/routes/index.ts:22` (ruta PATCH)
- `frontend/src/views/wizard.ejs:398-443` (listeners de auto-guardado)
- `frontend/src/views/partials/footer.ejs:28-33` (feedback visual)

**Verificación:** Build OK (`npm run build`)

---

## 15. Fix aplicado (2026-05-06)

### Bug 4 — Cambio de variante sin actualizar contenido

**Causa raíz identificada:**
Las funciones `selectRelato` e `initRelatos` estaban encapsuladas dentro de un IIFE
`(function() { ... })()`, lo cual podía causar problemas de scope en algunos contextos
de navegación HTMX.

**Fix aplicado:**
- Extraídas las funciones `selectRelato` e `initRelatos` del IIFE para que queden
  definidas en el scope global del script.
- Mantenido el event listener de click con delegación de eventos para robustness.
- Mantenidos los listeners `DOMContentLoaded` y `htmx:afterSwap` para inicialización.

**Archivo modificado:** `frontend/src/views/relatos.ejs:68-127`

---

### Bug 5 — Botón copiar no funciona

**Causa raíz identificada:**
La función `copyRelatoContent` usaba `navigator.clipboard.writeText()` sin manejo
de errores, lo que causaba fallos silenciosos (especialmente en contextos no-HTTPS
o cuando el elemento no existía).

**Fix aplicado:**
- Agregado `try/catch` con logging de errores a consola para debugging.
- Verificación de existencia del elemento antes de copiar.
- Verificación de que hay texto para copiar.
- Feedback visual mejorado en caso de error (icono de alerta + mensaje).

**Archivo modificado:** `frontend/src/views/relatos.ejs:129-164`

**Nota:** Si el problema persiste en producción, verificar que el sitio corra sobre
HTTPS o localhost (requisito de la Clipboard API).

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

---

### Bug 10 — Tabs de relatos no funcionan en primera entrada (hx-boost vs DOMContentLoaded)

**Síntoma reportado (2026-05-08):** Al navegar a `/historia/:id/relatos` desde la galería, los tabs (uno por relato) están visibles pero al hacer click no cambian el contenido del panel. Solo después de F5 funciona.

**Causa raíz:** El layout `partials/layout.ejs` tiene `<body hx-boost="true">`, lo que convierte toda navegación de `<a>` en peticiones HTMX que reemplazan el body sin recargar la página. Consecuencia:

- `DOMContentLoaded` **no se dispara** en una navegación hx-boost (la página ya estaba cargada).
- El listener `htmx:afterSwap` que registraba `relatos.ejs` se enganchaba *durante* la ejecución del swap actual, demasiado tarde para captar ese mismo evento — solo servía para swaps futuros.
- Resultado: `initRelatos()` nunca corría en la primera entrada → ni el primer tab se marcaba activo ni el handler de click delegado quedaba enganchado.

F5 funcionaba porque era una navegación full-page (sin hx-boost) y `DOMContentLoaded` sí se disparaba.

**Fix aplicado:** `frontend/src/views/relatos.ejs:88-114`:

- `activateFirstTab()` se invoca **inmediatamente** al evaluar el script (el `<script>` está al final del body, el DOM ya existe).
- El listener `click` delegado se mueve afuera de la función de inicialización y se protege con un flag `window.__relatosTabClickBound` para evitar duplicarse en navegaciones sucesivas (bajo hx-boost, `document` persiste entre swaps).
- Se mantiene `htmx:afterSwap → activateFirstTab` para re-activar el primer tab si el contenido se recarga vía HTMX.

**Lección reusable:** cualquier vista bajo el layout que dependa de inicialización JS al cargar debe ejecutarla *inmediatamente* dentro del script inline, no dentro de un listener `DOMContentLoaded`. Patrón a aplicar a futuros refactors si aparecen síntomas similares.

---

### Bug 11 — No se puede cancelar mid-stream durante una generación normal

**Estado:** [ ] INVESTIGATE / SPECIFY (abierto 2026-05-08).

**Descripción:** La función `cancelGeneration()` existe en `frontend/public/js/streaming-room.js:179` y funciona correctamente: cierra el EventSource, dispara un PATCH a `/api/v1/stories/:id/status` (presumiblemente para marcar la historia cancelada), y muestra el panel de error con un mensaje de cancelación. **Pero el botón que la invoca solo está renderizado dentro de `partials/streaming_error_panel.ejs`**, que solo se hace visible *después* de que ocurre un error o cuando ya se canceló.

**Síntoma:** durante una generación normal en curso (status=GENERANDO, beats en progreso) no hay forma de detener el proceso desde la UI. El usuario que cambia de opinión o detecta que algo va mal solo puede:
- Cerrar la pestaña (el backend puede no enterarse limpiamente, queda historia en `processing`).
- Esperar a que termine.
- Esperar a que falle.

**Comportamiento esperado:** un botón "Detener generación" visible mientras `setBadge` esté en `PROCESANDO`/`GENERANDO`, oculto en `COMPLETO` y `ERROR`.

**Decisiones de UX a tomar (no abordar todavía):**
- Ubicación: ¿botón discreto al lado del badge superior? ¿CTA bajo el spinner? ¿flotante sticky bottom-right?
- Confirmación: ¿modal de "¿Seguro? Perderás los beats ya generados"? Riesgo: agrega fricción si solo se quiere abortar rápido.
- Estado backend tras cancel mid-stream: ¿la historia queda `failed`, `cancelled` (status nuevo), `completed` con beats parciales, o `draft`? Coordinar con `streaming_service.py` y `StreamSessionManager` (Spec-201/210). El `cancelGeneration()` actual asume un PATCH ya implementado — verificar que el endpoint exista y haga lo correcto.
- Reintentar tras cancelar: ¿se reusa el mismo endpoint que `retryStream()` o necesita diferenciar?

**Archivos involucrados:**
- `frontend/src/views/streaming-room.ejs` — agregar botón en zona visible mientras corre el stream.
- `frontend/public/js/streaming-room.js:179` — la función ya existe, solo necesita un nuevo caller.
- `src/application/services/streaming_service.py` — verificar el handling del cierre de EventSource desde el cliente.

**Pre-trabajo de SPECIFY:** revisar si el `StreamSessionManager` (Spec-201) tiene un mecanismo de cancelación cooperativa, o si el cierre del EventSource desde el cliente solo cancela la conexión sin avisar al productor en backend.
