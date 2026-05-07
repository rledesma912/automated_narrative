# Spec-318: Sistema de Diseño Centralizado y Componentización UI

**Fecha:** 5 de mayo de 2026  
**Estado:** Draft / Specifying  
**Prioridad:** Media-Alta  
**Metodología:** SDD (Specify → Plan → Tasks → Implement)

---

## 1. Objetivo

Centralizar y normalizar el lenguaje visual de **NarrativeForge** eliminando la duplicación masiva de clases Tailwind (DRY) y extrayendo componentes reutilizables (SOLID/DIP). Se busca pasar de estilos "inline" dispersos a una arquitectura de diseño basada en componentes `@layer` y partials EJS, sin romper la compatibilidad con el sistema de temas dinámicos.

### Principios Guía:
- **No Breaking Changes:** El look & feel debe permanecer idéntico o mejorar levemente; la estructura de datos no cambia.
- **SOLID/DIP:** El HTML no debe depender de la implementación visual detallada, sino de abstracciones (ej. `.btn-forge`).
- **DRY:** Centralizar patrones repetitivos identificados en `home.ejs`, `gallery.ejs` y `wizard.ejs`.
- **KISS:** No sobre-abstraer; mantener Tailwind para layouts únicos.
- **UX:** Mejorar la consistencia de espaciados, estados hover y legibilidad tipográfica.

---

## 2. Componentes a Centralizar (Capa @layer components)

Se crearán las siguientes clases semánticas en `frontend/src/styles/globals.css`:

| Clase | Descripción | Comportamiento |
|---|---|---|
| `.btn-forge` | Botón primario de acción (estilo "Skull") | Tracking ancho, hover scale, sombra de acento. |
| `.btn-forge-outline` | Botón secundario para acciones de lista | Borde sutil, hover con opacidad. |
| `.card-forge` | Contenedor base de información | Fondo surface, borde variable, transición de color. |
| `.card-forge-active` | Estado activo/destacado de un card | Anillo de acento, elevación extra. |
| `.heading-forge-xl` | Títulos principales (Hero) | Fuente serif, tracking-tighter, color acento. |
| `.heading-forge-lg` | Títulos de sección | Fuente serif, borde inferior sutil. |
| `.badge-forge` | Etiquetas de estado (Generando, Error, OK) | Texto XS, tracking-widest, background semitransparente. |
| `.text-forge-body` | Cuerpo de texto normalizado | Interlineado relajado, color text variable. |

---

## 3. Arquitectura de Temas (Revisión)

Se mantiene el flujo actual pero se asegura la compatibilidad:
1. `themes.json` → Fuente de verdad de valores hexadecimales.
2. `ThemeService.toCssVars()` → Inyecta en `:root` del `layout.ejs`.
3. `tailwind.config.js` → Mapea `forge-*` a `var(--forge-*)`.
4. **Mejora:** Normalizar el uso de `--font-serif` y `--font-mono` para que cambien según el tema (Noir vs Horror).

---

## 4. Plan de Implementación (Slices)

### Slice 1: Infraestructura y CSS Base
- [x] **1.1** Actualizar `frontend/src/styles/globals.css` con las definiciones de `@layer components`.
- [x] **1.2** Asegurar que `tailwind.config.js` tenga todos los mapeos necesarios (especialmente espaciados y sombras).
- [x] **1.3** Test de compilación: `npm run build:css`.

### Slice 2: Refactor de Componentes Atómicos (Layout & Sidebar)
- [x] **2.1** Limpiar `sidebar.ejs`: usar `.nav-link-forge` (nueva abstracción).
- [x] **2.2** Limpiar `footer.ejs`: normalizar estados de conexión.
- [x] **2.3** Validar visualmente la consistencia del "chrome" de la aplicación.

### Slice 3: Refactor de Vistas de Contenido (Home & Gallery)
- [x] **3.1** Refactorizar `home.ejs`: aplicar `.heading-forge-xl` y `.card-forge`.
- [x] **3.2** Refactorizar `gallery.ejs`: aplicar `.card-forge` a los items de historia y `.badge-forge` a los estados.
- [x] **3.3** Refactorizar `wizard.ejs` y `generate.ejs`: normalizar inputs y botones.

### Slice 4: Mejoras de UX y Feedback
- [x] **4.1** Implementar transiciones globales de opacidad para cargas de página (HTMX).
- [x] **4.2** Normalizar el `modal_confirm.ejs` con los nuevos estilos de componentes.
- [x] **4.3** Asegurar accesibilidad (contraste base en todos los temas).

---

## 5. Checklist de Verificación (Validation)

- [x] `npm run build:css` genera el bundle sin warnings.
- [ ] Las vistas renderizan exactamente igual (o más consistentes) que antes.
- [ ] El cambio de tema en la sidebar actualiza correctamente todos los nuevos componentes `.forge-*`.
- [x] No hay estilos "hardcoded" de clases Tailwind (`red-500`, `blue-500`, etc.) fuera de `themes.json`. (Los colores en `guia.ejs` y `relatos.ejs` son casos específicos de contenido estático).
- [ ] Verificación de responsividad en componentes centralizados.

---

## 6. Riesgos y Mitigación

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Especificidad de CSS | Medio | Usar `@layer components` para que las utilidades de Tailwind sigan pudiendo sobreescribir casos puntuales. |
| Romper temas dinámicos | Alto | Mantener siempre la referencia a `var(--forge-*)` y nunca a colores estáticos. |
| Regresión visual | Bajo | Capturas de pantalla previas al refactor para comparación manual. |

---

## 7. Referencias

## 8. Extensión: Colores de Error Centralizados (Mayo 2026)

### 8.1 Problema Identificado

27 ocurrencias de colores hardcodeados para errores/estados en vistas EJS:

| Vista | Línea | Pattern |
|-------|-------|---------|
| streaming-room | 328,335,364,366,367,376,521 | `red-500`, `red-800`, `red-900`, `red-950` |
| wizard | 236,280,324,391 | `hover:text-red-400`, `btn-forge-outline !bg-red-900` |
| gallery | 8,95 | `!text-red-500`, `!text-red-400` |
| historia | 128 | `hover:text-red-400` |
| modal_confirm | 9,10,32 | `bg-red-950`, `text-red-500`, `!bg-red-900` |
| layout | 37 | `border-red-500`, `text-red-400` |
| home | 56 | `text-red-400/50` |
| footer | 87 | `bg-red-500` |
| guia | 11 | `--accent-blood: #8b0000` (CSS var) |
| debug | 23,39 | `bg-red-950`, `text-red-400` |

### 8.2 Solución

Agregar nuevas variables a `themes.json`:

```json
{
  "horror": {
    "error": "#ef4444",
    "error-bg": "#7f1d1d",
    "error-border": "#991b1b"
  }
}
```

Y crear clases utilitarias en `globals.css`:

```css
.text-forge-error { @apply text-[var(--forge-error)]; }
.bg-forge-error { @apply bg-[var(--forge-error-bg)]; }
.border-forge-error { @apply border-[var(--forge-error-border)]; }
.hover\:bg-forge-error:hover { @apply bg-[var(--forge-error-bg)]; }
```

### 8.3 Reemplazos a Realizar

| Pattern Original | Nuevo Clase |
|-----------------|-----------|
| `text-red-500` | `text-forge-error` |
| `text-red-400` | `text-forge-error` |
| `bg-red-950` | `bg-forge-error` |
| `bg-red-900` | `bg-forge-error` |
| `border-red-900` | `border-forge-error` |
| `hover:text-red-400` | `hover:text-forge-error` |
| `hover:bg-red-800` | `hover:bg-forge-error` |

### 8.4 Estado

- [x] Agregar variables a `themes.json` (todos los temas)
- [x] Extender `ThemeService.toCssVars()` para inyectar `--forge-error*`
- [x] Agregar clases utilitarias en `globals.css` (en `@layer utilities` para tener precedencia y soportar la variante `!`)
- [x] Reemplazar en `streaming-room.ejs`
- [x] Reemplazar en `wizard.ejs`
- [x] Reemplazar en `gallery.ejs`
- [x] Reemplazar en `historia.ejs`
- [x] Reemplazar en `modal_confirm.ejs`
- [x] Reemplazar en `layout.ejs`
- [x] Reemplazar en `footer.ejs`, `home.ejs`, `debug.ejs`
- [ ] `guia.ejs` — descartado: usa `--accent-blood` (= `forge-accent`), no es color de error semántico

**Notas de implementación:**
- Las clases `text/bg/border-forge-error` se definen en `@layer utilities` (no `components`) para ganar precedencia sobre las defaults de Tailwind y soportar el modificador `!important` (`!bg-forge-error`).
- No se agregaron `error*` a `colors.forge` en `tailwind.config.js` para evitar autogen colisionante: `bg-forge-error` debe apuntar a `--forge-error-bg` (oscuro), no a `--forge-error` (brillante).
- Se incluyeron explícitamente las variantes `\!` y `hover\:` en CSS para soportar el uso en EJS (`!bg-forge-error`, `hover:!bg-forge-error`).

### 8.5 Tests de Validación (Frontend/Vite)

Dado que el theming es frontend-only, los tests van en el pipeline de build:

```typescript
// frontend/src/__tests__/theme-vars.test.ts

import { describe, it, expect } from "vitest";
import themes from "../config/themes.json";

describe("Theme CSS Variables", () => {
  it("horror theme has error vars", () => {
    const theme = themes["horror"] as ThemeDef;
    expect(theme).toHaveProperty("error");
    expect(theme).toHaveProperty("error-bg");
    expect(theme).toHaveProperty("error-border");
  });

  it("all themes have error vars", () => {
    const keys = ["horror", "noir", "light-contrast"];
    keys.forEach((key) => {
      const theme = themes[key] as ThemeDef;
      expect(theme.error).toBeDefined();
      expect(theme["error-bg"]).toBeDefined();
      expect(theme["error-border"]).toBeDefined();
    });
  });
});

describe("CSS Build", () => {
  it("generates .text-forge-error class", async () => {
    // Post-build: verificar que las clases existen en el CSS generado
    const css = await readFile("dist/styles.css");
    expect(css).toContain("--forge-error");
  });
});
```

### 8.6 Checklist Final (Post-Reemplazos)

- [x] Agregar variables a `themes.json` (todos los temas)
- [x] Agregar clases utilitarias en `globals.css`
- [x] `npm run build:css` genera sin warnings
- [x] `npm run build` (tsc) pasa sin errores
- [x] `grep "red-[0-9]"` en `frontend/src/views/` no devuelve resultados
- [x] Reemplazar hardcoded colors en todas las vistas
- [ ] `npm run test` — 3 fallos preexistentes en `cutover-no-cdn.test.ts` por race condition con `build-succeeds.test.ts` (no introducido por este spec)

---

**¿Rompe la estrategia?** No. La extiende. El spec actual ya busca "eliminar duplicación" y "compatibilidad con temas dinámicos". Agregar variables de error centralizadas es exactamente alineado con esos objetivos.

Las 27 ocurrencias CANCELAN el checklist actual ("No hay estilos hardcoded fuera de themes.json") — por eso hay que agregarlas al spec.

- Spec-315: CSS Architecture (CLI vs CDN)
- Spec-301: Limpieza UI
- `CLAUDE.md`: CSS_ARCHITECTURE section

---

## 9. Extensión: Saneamiento de Vistas EJS (Mayo 2026)

### 9.1 Problema Identificado

Detectado durante el refactor de §8, dos vistas concentran complejidad estructural — no son "código mal escrito" sino acumulación orgánica que pide partials.

| Vista | Líneas | Smell |
|---|---|---|
| `wizard.ejs` | ~400 | Tres bloques casi idénticos (personajes / escenarios / reglas, líneas 230-342). Mismo patrón: card con header + lista de items con botón delete + botón "agregar". |
| `streaming-room.ejs` | ~520 | Mezcla template HTML + script JS inline (lógica de stream + retry + parsing) + clases Tailwind largas en línea. |

### 9.2 Solución Propuesta

**`wizard.ejs` → Partial parametrizado**

Crear `frontend/src/views/partials/wizard_card_list.ejs` que reciba:
- `groupName` ('personajes' / 'escenarios' / 'reglas')
- `meta` (título, subtítulo)
- `cards` (índices)
- `maxCount`
- `regex` para `groupFieldsByIndex`
- `addLabel`, `addIcon`, `itemLabel` ("PERSONAJE" / "ESCENARIO" / "REGLA")
- `deleteHandler` ('askDeletePersonaje' / etc.)

Beneficio estimado: wizard.ejs baja de ~400 a ~200 líneas; un solo lugar para tocar la UX de listas dinámicas.

**`streaming-room.ejs` → Separar concerns**

- Extraer el `<script>` inline a `frontend/src/public/js/streaming-room.js` y referenciarlo con `<script src="/js/streaming-room.js" defer>`.
- Mover el panel de error y el panel done a partials (`partials/streaming_error_panel.ejs`, `partials/streaming_done_panel.ejs`).
- El template principal queda solo con estructura + slots.

### 9.3 Plan de Implementación (Slices)

- **9.A** Crear `wizard_card_list.ejs`, migrar bloque `personajes` y validar visualmente.
- **9.B** Migrar `escenarios` y `reglas` al mismo partial; eliminar duplicación.
- **9.C** Extraer `<script>` de `streaming-room.ejs` a archivo JS estático servido por Express.
- **9.D** Extraer paneles a partials.
- **9.E** Validar paridad visual (capturas antes/después) y comportamiento (start/cancel/retry).

### 9.4 Estado

- [x] 9.A — wizard_card_list.ejs cableado para `personajes` (rediseño con API explícita de 15 locals; ver §9.6).
- [x] 9.B — migración `escenarios` y `reglas` al mismo partial (3 invocaciones en `wizard.ejs:214, 238, 260`). wizard.ejs: 635 → 624 líneas (reducción modesta porque el partial es más grande que un inline mínimo, pero la duplicación entre los 3 grupos quedó eliminada).
- [x] 9.C — extracción JS streaming-room (`public/js/streaming-room.js`, paridad 1:1 con inline)
- [x] 9.D — extracción paneles a partials (`streaming_done_panel.ejs`, `streaming_error_panel.ejs`); cableados en `streaming-room.ejs` con `<%- include(...) %>`
- [x] 9.E — validación SSE end-to-end:
  - Render local de los 3 modos (sse-regenerate / monitor / lectura) sin errores EJS.
  - Regeneración real (PATCH status=processing → SSE → 5 beats → done) verificada vía curl: shape de eventos `status / beat_start / beat_done / heartbeat / done` coincide con el que escucha `streaming-room.js`.
  - HTTP 200 en `/generar/stream/:id`, `/generar/stream/:id?regenerate=1` y modo monitor (`status=processing` desde otra sesión).
  - `streaming-room.ejs`: 695 → 377 líneas (-46%).
  - **No probado en navegador real:** animaciones (dots, lucide), `cancelGeneration` mid-stream, `retryStream` tras error, modo monitor en pestaña paralela.

### 9.5 No-objetivos

- No reescribir lógica de stream (eso vive en `streaming_service.py`, lado backend; ver Spec-500).
- No cambiar el wizard de 5 pasos (Spec-220 sigue siendo la referencia).
- No tocar HTMX swaps ni endpoints — solo refactor estructural de templates.

### 9.6 Bloqueo de §9.A/B — rediseño del partial necesario

El partial `wizard_card_list.ejs` tal como existe **no encaja con `wizard.ejs`** porque asume convenciones que no coinciden:

| Aspecto | Partial asume | wizard.ejs real |
|---|---|---|
| ID cards | `${pfx}-card-${idx}` | `personaje-card-`, `scenario-card-`, `rule-card-` |
| ID msg max | `msg-max-${pfx}` | `msg-max-personajes` (plural distinto a `personaje`) |
| Add handler | param genérico `addHandler` | `addPersonaje()`, `addScenario()`, `addRule()` |
| Delete handler | param genérico `deleteHandler` | `askDeletePersonaje`, `askDeleteScenario`, `askDeleteRule` |
| Max count | un solo `maxCount` | `MAX_PROTAGONISTAS=5`, `MAX_ESCENARIOS=4`, `MAX_REGLAS=7` |

Pasar `pfx='personaje'` rompe `msg-max-personajes`; pasar `pfx='personajes'` rompe los IDs de cards que el JS busca.

**Opciones evaluadas:**

a) Refactorizar el partial para aceptar mapa explícito de IDs (`cardIdPrefix`, `msgMaxId`, `addHandler`, `deleteHandler`) en lugar de derivar todo de un único `pfx`.
b) Renombrar IDs/handlers en `wizard.ejs` y su `<script>` para uniformar al partial.
c) Posponer §9.A/B (es solo refactor, no cambia funcionalidad).

**Resolución (2026-05-07):** se ejecutó la **opción (a)**. El partial ahora recibe 15 locals explícitos (`groupContainerId`, `cardIdPrefix`, `deleteBtnIdPrefix`, `addBtnId`, `msgMaxId`, `addHandler`, `deleteHandler`, `itemLabel`, `addLabel`, `maxLabel`, `iconAdd`, `meta`, `indices`, `cards`, `saved` + opcional `labelIdPrefix`, `fieldNamePrefix`). Sin convenciones implícitas; cada call-site declara qué IDs usa. Tres invocaciones en `wizard.ejs:214, 238, 260` cubren personajes / escenarios / reglas con sus IDs originales preservados, así el `<script>` del wizard sigue funcionando sin cambios.

---

## 10. Extensión: Unificación de Estilos de Botones (Mayo 2026)

### 10.1 Problema Identificado

Actualmente coexisten dos estrategias de styling para botones:

1. **Clases CSS centralizadas**: `.btn-forge`, `.btn-forge-outline` (en `globals.css`)
2. **Tailwind inline**: clases como `bg-forge-accent text-forge-text px-6 py-3 hover:bg-forge-error` dispersas en los EJS

Esto genera inconsistencia visual y viola DRY. Ejemplo en `streaming-room.ejs` línea 328:

```html
<!-- Estilo inline ( Tailwind puro) -->
<button class="px-12 py-5 bg-forge-accent text-forge-text text-lg tracking-[0.4em] ...">

<!-- vs clase centralizada (CSS unificado) -->
<button class="btn-forge">
```

### 10.2 Decisión de Arquitectura

**Regla:** Usar clases CSS unificadas (`.btn-forge*`) como abstracción principal. **NO** usar Tailwind inline para patrones de botones que se repiten.

**Excepciones válidas para Tailwind inline:**
- Casos muy puntuales que no se repiten (un solo botón en toda la app)
- Override de una propiedad específica (ej: `class="btn-forge !text-red-500"`)

### 10.3 Variantes de Botones a Crear

Para soportar todos los casos de uso sin romper existentes, agregar a `globals.css`:

| Clase | Descripción | Uso |
|---|---|---|
| `.btn-forge` | Botón primario estándar | Principal call-to-action |
| `.btn-forge-lg` | Botón primario grande | Heroes, acciones principales |
| `.btn-forge-sm` | Botón primario pequeño | Inline actions |
| `.btn-forge-outline` | Botón secundario | Secondary actions |
| `.btn-forge-outline-sm` | Botón secundario pequeño | Items de lista |
| `.btn-forge-danger` | Botón de peligro | Delete, confirmaciones destructivas |

### 10.4 Plan de Implementación (Slices)

**Slice 10.A: Agregar variantes de botones**
- [ ] Agregar `.btn-forge-lg`, `.btn-forge-sm`, `.btn-forge-outline-sm`, `.btn-forge-danger` en `globals.css`
- [ ] Compilar: `npm run build:css`
- [ ] Validar que todos los temas funcionen

**Slice 10.B: Reemplazar botones inline en streaming-room.ejs**
- [ ] Línea 251, 257 → `.btn-forge-outline-sm`
- [ ] Línea 328, 335 → `.btn-forge-lg`
- [ ] Línea 366 → `.btn-forge`
- [ ] Línea 397, 577 → `.btn-forge-sm`

**Slice 10.C: Reemplazar botones inline en historia.ejs**
- [ ] Línea 141 → `.btn-forge`
- [ ] Línea 156, 179 → `.btn-forge-sm`

**Slice 10.D: Reemplazar botones inline en wizard-confirm.ejs**
- [ ] Línea 61, 70 → `.btn-forge-sm`

**Slice 10.E: Validación final**
- [ ] No quedan botones con `bg-forge-accent text-forge-text` inline en vistas
- [ ] Verificación visual en todos los temas (horror, noir, light-contrast)
- [ ] `npm run build:css` sin warnings

### 10.5 Estado

- [x] 10.A — Variantes de botones en `globals.css:22-71` (`.btn-forge`, `.btn-forge-outline`, `.btn-forge-lg`, `.btn-forge-sm`, `.btn-forge-outline-sm`, `.btn-forge-danger`).
- [x] 10.B — Reemplazo en `streaming-room.ejs` (re-aplicado 2026-05-08 sobre el código real, las líneas que el spec citaba antes eran obsoletas tras Spec-318 §9):
  - "Ver historia" (link outline) → `.btn-forge-outline`
  - 2× "Regenerar" (link/button bg-accent sm) → `.btn-forge-sm`
  - 2× "Iniciar generación / regeneración" (px-12 py-5 lg) → `.btn-forge-lg group` (clase `group` preservada para `group-hover:rotate-12` del icono sparkles).
- [x] 10.C — Reemplazo en `historia.ejs` (re-aplicado 2026-05-08):
  - "Comenzar Generar/Regenerar" (px-8 py-4 hero) → `.btn-forge flex-1`
  - "Editar" + "Ver Relatos" (outline border-muted) → `.btn-forge-outline`
  - 2× "Regenerar"/"Generar" (bg-accent sm) → `.btn-forge-sm`
  - **Excepción documentada**: "Generar Relato" (`historia.ejs:147-152`) usa variante outline-accent (`border-forge-accent` + `text-forge-accent`) que es la única instancia. Se dejó inline con comentario `<%/* Variante outline-accent única; YAGNI sobre crear .btn-forge-outline-accent. */%>`. Si aparece otro caso, recién crear la clase.
- [x] 10.D — `wizard-confirm.ejs` ya usaba `.btn-forge-sm` (verificado en sesión).
- [x] 10.E — Validación post-2026-05-08: 0 botones inline grandes restantes (regex `class="[^"]*\bpx-[0-9]+ py-[0-9]+[^"]*(uppercase|tracking)[^"]*"` filtrando `btn-forge` no devuelve nada). Los `bg-forge-accent` que persisten en `home.ejs:21,36,58` y `wizard.ejs:163,183` son **decorativos** (círculos de iconos, líneas del stepper, divs informativos), no botones — fuera del alcance del spec.

### 10.6 Checklist de Verificación

- [x] Todos los botones primarios usan `.btn-forge*` (excepto Generar Relato outline-accent documentado).
- [x] Todos los botones secundarios usan `.btn-forge-outline*`.
- [x] No hay duplicación de estilos en vistas (verificado por grep).
- [ ] Cambio de tema actualiza correctamente todos los botones (validación humana pendiente).
- [ ] Look & feel se mantiene idéntico o mejora (validación humana pendiente).

---

## 11. Cierre del desacoplamiento frontend (2026-05-08)

Sesión dedicada a completar lo que §9 dejó a medias y limpiar deuda zombie. Resultado: **sin scripts inline grandes en vistas** (solo inyección de variables `window.X`), **botones unificados a `.btn-forge*`**, **vestigios de markdown removidos**.

### 11.1 Extracciones JS (patrón Spec-318 §9.C)

Cada vista con `<script>` inline real fue migrada a un archivo en `frontend/public/js/`. El patrón estándar es:

```ejs
<%/* inyección mínima de variables del servidor */%>
<script>
  window.X = "<%= server_var %>";
</script>
<script src="/js/<view>.js" defer></script>
```

El JS externo lee de `window.X` para mantener paridad 1:1.

| Vista | EJS antes → después | Archivo extraído | Nota |
|---|---|---|---|
| `relatos.ejs` | 225 → 84 (-63%) | `relatos.js` (117 líneas) | + borrado `<style>.prose</style>` muerto que dejó Bug 6 |
| `wizard.ejs` | 624 → 335 (-46%) | `wizard.js` (310 líneas) | mantiene `closeDeleteModal/addPersonaje/addScenario/addRule/askDelete*` como `window.X` para `onclick="..."` |
| `historia.ejs` | 203 → 171 (-16%) | (eliminado en Slice 3.6) | `historia.js` se extrajo y luego se borró completo: era zombie de funciones markdown |
| `partials/footer.ejs` | 94 → 40 (-57%) | `footer.js` (77 líneas) | + **fix de leak**: `window.__footerIntervalId` previene acumulación de `setInterval` bajo `hx-boost`; intervalo cambiado de 5s a 15s |
| `streaming-room.ejs` (modo monitor) | (bloque inline 86 líneas) → eliminado | `streaming-monitor.js` (119 líneas) | + **fix de bug latente**: `DOMContentLoaded` reemplazado por ejecución inmediata + `htmx:afterSwap` (mismo patrón que Bug 10 de Spec-316) |

**Estado final del JS inline (por vista):**

| Vista | Inline restante | Justificación |
|---|---|---|
| `streaming-room.ejs` | 8 líneas | Solo `window.STREAM_URL`, `STORY_ID`, `TOTAL_BEATS`, `MONITOR_STREAM_URL` (inyección variables) |
| `wizard.ejs` | 3 líneas | Solo `window.STEP_NUM` |
| `partials/layout.ejs` | 23 líneas | `lucide.createIcons` + autofocus + listeners HTMX globales — pertinentes al chrome global |
| `partials/modal_confirm.ejs` | 7 líneas | Flash modal — chico, no amerita extracción |

### 11.2 Limpieza de vestigios markdown (Slice 3.6)

Las funciones de gestión del archivo `.md` exportado (ver / descargar / eliminar) ya no existen funcionalmente — las rutas correspondientes habían sido removidas de `routes/index.ts` hace tiempo, pero quedaron handlers, vistas referenciadas y JS huérfanos.

**Eliminado:**
- `historia.ejs`: bloque `<% if (story.file_path) %>` con link "Ver Markdown" + botón "Eliminar Markdown" (-13 líneas).
- `historia.js`: archivo borrado completo (sólo contenía `confirmDeleteMarkdown`).
- `historia.controller.ts:97-170`: 3 handlers dead (`confirmDeleteMarkdownModal`, `verMarkdownHandler`, `downloadMarkdownHandler`) — 74 líneas.
- `streaming_done_panel.ejs`: botón `<a id="download-md-btn">` "Descargar Markdown".
- `streaming-room.js`: simplificación de `showDone(filePath)` → `showDone()` sin parámetro; 3 callers ajustados.

**Auditoría:** la vista `visualizar_markdown.ejs` que el handler eliminado referenciaba **nunca existió** en `views/` — era un bug de runtime esperando ser invocado. Las rutas `/ver-markdown`, `/descargar-markdown`, `/internal/historia/:id/markdown` no estaban registradas en `routes/index.ts`. Era código zombie completo.

**Imports preservados:** `fs`, `path`, `OUTPUT_DIR` siguen usados en `deleteStoryHandler` para borrar el archivo `.md` asociado al eliminar una historia (cleanup correcto).

**Backend:** el SSE event `done` sigue emitiendo `file_path` en el payload desde `streaming_service.py`. El frontend ya no lo lee, pero el campo no rompe nada. Limpieza opcional de un slice backend aparte si se quiere.

### 11.3 Bug latente arreglado de regalo (relatos.ejs Bug 10 reusado)

**`streaming-monitor.js` (modo monitor):** el inline original usaba `window.addEventListener("DOMContentLoaded", monitorAttach)`. Bajo `<body hx-boost="true">` ese evento NO se dispara en navegaciones internas → si entrabas a la sala monitor desde otra vista (galería, historia) sin F5, **el SSE del modo monitor nunca se conectaba**. Re-aplicado el patrón ya validado en relatos.js (Bug 10 de Spec-316): ejecución inmediata del script + listener `htmx:afterSwap` para re-attach.

### 11.4 Migración de botones a `.btn-forge*` (Slice 4)

Ver §10.5 actualizada con el resultado real post-2026-05-08. 10 botones migrados (5 en `historia.ejs`, 5 en `streaming-room.ejs`); 1 dejado inline deliberadamente (variante outline-accent única).

### 11.5 Resumen cuantitativo

```
EJS reducido:
  relatos.ejs       225 →  84  (-141, -63%)
  wizard.ejs        624 → 335  (-289, -46%)
  historia.ejs      203 → 171  ( -32, -16%)
  streaming-room    379 → 292  ( -87, -23%)
  footer (partial)   94 →  40  ( -54, -57%)

JS extraído (frontend/public/js/):
  relatos.js          117 líneas
  wizard.js           310 líneas
  footer.js            77 líneas (con fix de leak)
  streaming-monitor   119 líneas (con fix DOMContentLoaded)

Código zombie eliminado:
  historia.controller.ts   -74 líneas (3 handlers dead)
  historia.js               -19 líneas (archivo borrado)
  streaming_done_panel       -3 líneas (botón download)
  streaming-room.js          -8 líneas (simplificación showDone)
  relatos.ejs               -31 líneas (style.prose muerto)
                          ─────────────
                            ~135 líneas zombie eliminadas
```

### 11.6 Validación humana pendiente al cierre

- Modo monitor SSE desde otra pestaña sin F5 (Slice 3.5).
- Done-panel sin botón "Descargar Markdown" (Slice 3.6).
- Paridad visual de botones en los 3 temas: horror / noir / light-contrast (Slice 4).
- Footer activity widget sigue actualizando 1 vez cada 15s sin acumulación (Slice 2.5).
