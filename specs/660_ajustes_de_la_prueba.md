# SPEC-660: Ajustes de la prueba (escribir sin página intermedia, borrar personajes)

**Fecha:** 2026-10-10
**Tipo:** SDD — UI (frontend; el Core no cambia)
**Estado:** SPECIFY ✅ (2026-10-10: B1 camino B; B2 variante A, tacho en el acto; maquetas https://claude.ai/artifact/QcAzCxbF7bwrKuJmjhLa19) · PLAN ✅ (OK 2026-10-10) · TASKS ✅ (OK 2026-10-10) · S1 ✅ · S2 ✅ · S3 ✅ (2026-10-10) · **en prod** `cafc287` (PR #67 → #68)
**Rama:** propia, desde `development` después del PR de la Spec-650 (decisión del usuario 2026-10-10)
**Cambia:** Spec-630 B14 («siempre por la sala con `?escribir=1`») y B7 (borrar personajes).

---

## ASSUMPTIONS

1. Lo reportó el usuario probando la Spec-650 en dev (2026-10-10, capturas en la conversación).
2. El Core no cambia: `POST /stories/{id}/jobs` (`full_generation`) ya responde 202, o 409 con el job en curso.
3. `ForgeConfirm` (Spec-550 H8) es la única confirmación del sitio; se le puede sumar una nota y un ícono sin romper `hx-confirm`.
4. Las estimaciones ya llegan a «Los actos» y «El relato» (`loadEstimates`, Spec-510).
5. Textos en tono coloquial (Spec-580) y sin jerga (`sin-jerga.view.test.ts`).

---

## OBJECTIVE

**B1.** Hoy «Escribir el relato» (en «Los actos») y «Regenerar historia» (en «El relato») llevan a la sala, que **vuelve a preguntar** en una página que parece que ya arrancó («Escribiendo tu relato · Conectando… · Iniciando», los círculos de los actos) y con la pregunta y el botón **abajo de todo**, fuera de la pantalla. Que se confirme **donde se tocó el botón**, con el diálogo de siempre, y que la sala muestre **solo el progreso**.

**B2.** En «Quiénes están» de un acto, la «×» al lado de un personaje lo **borra de toda la historia**, pero el aviso dice «Se quita del acto 1» (los actos donde está marcado) y parece que lo saca del acto que se mira. Que quede claro qué hace cada cosa: la casilla del chip lo saca de **este** acto; borrar lo saca de **la historia**.

---

## 1. Relevamiento

| Dónde | Qué hay hoy |
|---|---|
| `asistente/escaleta.ejs:24` | `<a data-generar href="/generar/stream/{id}?escribir=1">`; `asistente.js:810` hace `flushAll()` y navega |
| `relatos.ejs:34` | «Regenerar historia» → `?escribir=1` |
| `streaming-room.ejs:81–95` (modo lectura) | «Regenerar historia» / «Escribir el relato» → `?escribir=1`; si falló, `POST /historia/{id}/generar` |
| `streaming-room.ejs:158–193` | `#start-panel` con `regenerateMode` / `startMode` y `initiateGeneration()` / `initiateRegeneration()` |
| `streaming-room.js:329` | `startJob()`: `POST …/jobs` → 202/409 → se ata al job |
| `confirm-dialog.js` | `ask({title, message, confirmLabel})`, ícono fijo de advertencia |
| `asistente/_acto.ejs:178`, `asistente.js:476` | «×» → `borrar()` con «Se quita del acto N» → `POST …/characters/remove` |
| Tests | E2E `streaming-room`, `relatos`, `asistente`, `estimates`, `generation-guard`; unit `relatos.view`, `estimates.view`, `stream.controller`; fixture `tests/fixtures/asistente/escaleta.html` |

---

## 2. Qué cambia

### B1 — Confirmar donde se toca el botón

- Un solo módulo nuevo (`public/js/escribir-relato.js`) para todos los botones `[data-escribir-relato]`: en «Los actos» (antes guarda lo pendiente, `flushAll`), en «El relato» y en la sala en modo lectura (incluido el caso fallido, que deja el `POST /historia/{id}/generar`).
- Al tocar: `ForgeConfirm.ask` con título, tiempo estimado y, si ya hay versiones, «Se escribe una versión nueva; las que tenés quedan en «El relato»». Aceptar → `POST /stories/{id}/jobs` → 202 o 409 → va a `/generar/stream/{id}`, que se ata sola al job activo.
- Si el POST falla (sin red, 422, 5xx): el error se muestra donde se tocó (nota), no se navega.
- La sala pierde `#start-panel`, `startMode` y `regenerateMode`. `?escribir=1` y `?regenerate=1` siguen andando para links viejos o pestañas abiertas: si no hay job, muestran la sala en modo lectura (que tiene el botón con el diálogo).
- `ForgeConfirm.ask` suma `note` (texto de una nota de info) e `icon` (`alert-triangle` por defecto; `feather` para escribir), sin cambiar a quienes ya lo usan.

### B2 — Borrar un personaje (texto e ícono)

- La «×» pasa a ser un **tacho** (`trash-2`) con la pista «Borrar de la historia».
- El aviso dice lo que pasa: «¿Borrar a «Don Raúl» de la historia?» / «Desaparece de todos los actos (hoy está en el acto 1). Para sacarlo solo de este acto, destildalo.». Sin actos: «No aparece en ningún acto.»
- Lo mismo para lugares (`data-borrar-lugar`), que tienen el mismo patrón.
- Decidido (2026-10-10): variante A, el tacho queda en la tarjeta del acto. La variante B (borrar solo desde una lista de personajes) se descartó.

---

## 3. SUCCESS CRITERIA

1. Desde «Los actos», «El relato» y la sala en modo lectura: un clic → diálogo con el tiempo estimado → aceptar → la sala con el progreso en marcha. Nunca aparece «¿Empezamos a escribir?» ni «¿Regeneramos la historia?» en la sala.
2. Cancelar el diálogo no crea ningún job. Con un job en curso (409) se va a la sala de ese job.
3. `?escribir=1` sin job no rompe: muestra la sala en modo lectura.
4. El aviso de borrar un personaje o un lugar dice «de la historia» y en qué actos estaba; el ícono no es una «×».
5. `sin-jerga`, `gramatica-visual`, `no-native-dialogs` y `no-hardcoded-colors` en verde; Vitest, Playwright y pytest en verde; dev con el cambio.

## BOUNDARIES

- **Always:** maquetas antes de implementar (OK del usuario); textos coloquiales; un solo diálogo (`ForgeConfirm`).
- **Ask first:** sacar el borrado de la tarjeta del acto (alternativa de B2); tocar el Core.
- **Never:** diálogos nativos; lanzar un job sin confirmación.

## OPEN QUESTIONS

- (ninguna: B2 resuelto con la variante A)

---

## 4. PLAN (2026-10-10)

Relevado en `feat/spec-660-ajustes-de-la-prueba` (desde `development` `86270d6`). El Core no cambia.

### 4.1 Decisiones

| # | Riesgo / duda | Decisión recomendada |
|---|---|---|
| D1 | ¿Cuándo va la nota «Se escribe una versión nueva…»? | Cuando la historia está `completed` (hoy es el mismo criterio que `regenerateMode`). El botón lo lleva en `data-version-nueva`. |
| D2 | La sala en modo lectura con una historia **fallida** tiene un `<form POST /historia/{id}/generar>` que **lanza sin confirmar**. | El botón pasa a ser `[data-escribir-relato]` como los demás. La ruta POST queda solo para links viejos y **redirige a la sala** sin lanzar nada (así ningún camino lanza sin confirmar). |
| D3 | «Reintentar» del panel de error lanza un job nuevo sin preguntar si el anterior ya terminó. | Si el job sigue vivo, se vuelve a atar (como hoy); si no, abre el mismo diálogo de escribir. |
| D4 | `?escribir=1` / `?regenerate=1` sin job (links viejos, pestañas abiertas, historial). | Muestran la sala en modo lectura, que tiene el botón con el diálogo. No se abre el diálogo solo. |
| D5 | El POST falla (sin red, 422, 5xx). | El diálogo se cierra, el botón vuelve a su estado y aparece una `nota-forge--error` al lado del botón con un texto coloquial. No se navega. |
| D6 | Doble clic / dos pestañas. | El botón sigue siendo `[data-generation-trigger]` (lo bloquea `generation-guard.js` mientras hay un job) y queda «Arrancando…» desde que se acepta; un 409 lleva a la sala del job que ya corre. |
| D7 | Cambiar el ícono del diálogo sin romper `hx-confirm`. | `confirm_dialog.ejs` trae los tres íconos ya dibujados (`aviso` por defecto, `escribir` = pluma, `borrar` = tacho en rojo) y `ask({icon, note})` muestra uno; sin `icon` se ve igual que hoy. |

### 4.2 Qué se toca

| Lugar | Cambio |
|---|---|
| `partials/confirm_dialog.ejs`, `public/js/confirm-dialog.js` | `icon` (`aviso`/`escribir`/`borrar`) y `note` (nota de info, oculta si no viene) |
| **Nuevo** `public/js/escribir-relato.js` (UMD, testeable en Vitest como `eta.js`) | Click en `[data-escribir-relato]`: en el asistente, `await ForgeAsistente.flushAll()` → `ForgeConfirm.ask` → `POST /api/v1/stories/{id}/jobs` → 202/409 → `/generar/stream/{id}`; si falla, D5. Textos con el estimado de `data-estimado` |
| `layout` (`<head>`) | Cargar `escribir-relato.js` (defer, con `?v=`), como `confirm-dialog.js` |
| `asistente/escaleta.ejs` + `asistente.js:810` | El `<a data-generar>` pasa a `<button data-escribir-relato …>`; `asistente.js` deja de navegar; el guardado lo pide `escribir-relato.js` (`ForgeAsistente.flushAll`) |
| `relatos.ejs:34` | «Regenerar historia» → `<button data-escribir-relato data-version-nueva>` |
| `streaming-room.ejs` | Modo lectura: los tres botones (completed / failed / draft) → `[data-escribir-relato]` (D2). Se van `#start-panel`, `regenerateMode` y `startMode`; la vista «en vivo» se muestra solo con un job activo |
| `stream.controller.ts` | Sin `regenerateMode` / `startMode` (D4) |
| `streaming-room.js` | Se van `initiateGeneration` / `initiateRegeneration` / `startJob` / `showStarting`; `retryStream` según D3 |
| `historia.controller.ts` `generarDesdeHistoria` | Redirige a la sala sin lanzar (D2) |
| `asistente/_acto.ejs` | La «×» de personajes y lugares → tacho (`trash-2`), `title` «Borrar de la historia»; pista de «Quiénes están»: «Destildá a alguien para sacarlo de este acto.» |
| `asistente.js` `borrar()` | Títulos «¿Borrar a «X» de la historia?» / «¿Borrar el lugar «X» de la historia?»; texto «Desaparece de todos los actos (hoy está en el acto 1). Para sacarlo solo de un acto, destildalo en ese acto.» (lugar: «…elegí otro lugar en ese acto.»); sin usos: «No aparece en ningún acto.»; `icon: "borrar"` |
| Comentarios y CLAUDE.md | B14 de la 630 («siempre por la sala con `?escribir=1`») queda reemplazado por esta spec |

### 4.3 Tests

| Test | Cambio |
|---|---|
| **Nuevo** Vitest `escribir-relato.test.ts` | Cancelar no hace POST; 202 y 409 navegan a la sala; error → nota y botón restaurado; nota de versión nueva solo con `data-version-nueva`; guarda lo pendiente antes del POST |
| Vitest `confirm-dialog` (nuevo o el existente) | `icon` y `note`; sin ellos, igual que hoy |
| `stream.controller.test.ts` (10), `estimates.view.test.ts` (22), `relatos.view.test.ts` (3), `escaleta.view.test.ts` | Sin `start-panel`; los botones llevan `data-escribir-relato` y `data-estimado`; tacho en vez de «×» |
| E2E `streaming-room` (8), `relatos` (5), `generation-guard` (5), `asistente` (4), `estimates` (2), `relato-corto` (2) | Arrancar = botón → diálogo → aceptar → sala en marcha; uno nuevo: cancelar el diálogo no crea job; `?escribir=1` sin job = modo lectura |
| E2E `escaleta-elenco-y-lugares` | Los textos nuevos del aviso |
| Fixtures `tests/fixtures/asistente/` | `UPDATE_FIXTURES=1` y revisar el diff |
| Guardianes | `sin-jerga`, `gramatica-visual`, `no-native-dialogs`, `no-hardcoded-colors` en verde |

### 4.4 Slices

1. **S1 — Borrar con tacho (B2) + `ForgeConfirm` con ícono y nota.** Chico e independiente; deja el diálogo listo para S2.
2. **S2 — Escribir desde el botón (B1).** `escribir-relato.js` y los tres orígenes; la sala todavía conserva su panel (nadie llega a él).
3. **S3 — La sala solo muestra progreso.** Se van el panel, los modos y `startJob`; D2–D4; E2E y CLAUDE.md.

Cada slice cierra con tests en verde y dev mostrando el cambio (URL para mirar).

---

## 5. TASKS (2026-10-10)

### S1 — Borrar con tacho + diálogo con ícono y nota

- **T1.1** `confirm_dialog.ejs`: los tres íconos (`aviso`, `escribir`, `borrar`) y una `nota-forge--info` oculta. `confirm-dialog.js`: `ask({ …, icon, note })`; muestra el ícono pedido (por defecto `aviso`) y la nota solo si viene; al cerrar deja todo como estaba. **Hecho cuando:** Vitest nuevo `confirm-dialog.test.ts` (ícono por defecto, `escribir`, `borrar`, nota sí/no, `hx-confirm` sin cambios) en verde.
- **T1.2** `_acto.ejs`: la «×» de personajes y de lugares → `trash-2`, `title`/`aria-label` «Borrar … de la historia»; pista de «Quiénes están» con «Destildá a alguien para sacarlo de este acto.». **Hecho cuando:** `escaleta.view.test.ts` verifica el tacho y la pista; `gramatica-visual` y `no-hardcoded-colors` en verde.
- **T1.3** `asistente.js` `borrar()`: títulos y textos del §4.2 con `icon: "borrar"`. **Hecho cuando:** E2E `escaleta-elenco-y-lugares` con los textos nuevos («de la historia», «hoy está en el acto 2», «No aparece en ningún acto»).
- **T1.4** Fixtures `tests/fixtures/asistente/` con `UPDATE_FIXTURES=1` (diff revisado). Cierre: pytest, Vitest, Playwright y lint en verde; `make dev-status`; mirar en `https://storymaker.test/asistente/{id}/escaleta`.

### S2 — Escribir desde el botón

- **T2.1** Nuevo `public/js/escribir-relato.js` (UMD): click en `[data-escribir-relato]` → `ForgeConfirm.ask({ icon: "escribir", title, message con data-estimado, note si data-version-nueva })` → `POST /api/v1/stories/{id}/jobs` `{kind: "full_generation"}` → 202/409 con `job_id` → `location` a `/generar/stream/{id}`; si no, D5 (nota de error al lado, botón restaurado). Busy «Arrancando…» desde que se acepta (D6). Cargado en el `<head>` del layout. **Hecho cuando:** Vitest `escribir-relato.test.ts` (cancelar = sin POST; 202 y 409 navegan; 422/5xx/sin red = nota y sin navegar; nota de versión nueva solo con el atributo; guarda lo pendiente antes).
- **T2.2** «Los actos»: `escaleta.ejs` → `<button data-escribir-relato data-generation-trigger data-story-id data-estimado [data-version-nueva si completed]>`; `asistente.js` saca el handler de `data-generar` (el guardado lo pide `escribir-relato.js` con `ForgeAsistente.flushAll`).
- **T2.3** «El relato»: `relatos.ejs` → `<button data-escribir-relato data-version-nueva …>`.
- **T2.4** Sala en modo lectura: los tres botones (completed / failed / draft) → `[data-escribir-relato]` (D2: sale el `<form POST>`).
- **T2.5** Tests de vista (`estimates.view`, `relatos.view`, `escaleta.view`) con los atributos nuevos. Cierre de slice como en S1; mirar «Los actos» y «El relato» en dev.

### S3 — La sala solo muestra progreso

- **T3.1** `stream.controller.ts` sin `regenerateMode` / `startMode`; `streaming-room.ejs` sin `#start-panel`; la vista «en vivo» solo con job activo; `?escribir=1` sin job = modo lectura (D4). **Hecho cuando:** `stream.controller.test.ts` lo cubre.
- **T3.2** `streaming-room.js`: fuera `initiateGeneration`, `initiateRegeneration`, `startJob`, `showStarting`; `retryStream` según D3 (job vivo → se ata; si no, el diálogo de escribir).
- **T3.3** `generarDesdeHistoria` redirige a la sala sin lanzar (D2). Test unitario del controlador.
- **T3.4** E2E: `streaming-room`, `relatos`, `generation-guard`, `asistente`, `estimates`, `relato-corto` arrancan con botón → diálogo → aceptar; nuevos: cancelar no crea job, `?escribir=1` sin job muestra modo lectura, POST viejo no lanza.
- **T3.5** CLAUDE.md (Galería / B14 → Spec-660), memoria, PR a `development`. Cierre: todo en verde y dev con el cambio.

---

## 6. Notas de la implementación (2026-10-10)

- **Texto del diálogo con versiones:** «¿Regeneramos la historia?» / «Regenerar historia» (no «Escribir de nuevo» de la maqueta), para coincidir con el botón de «El relato» y la B19 de la Spec-630.
- **Doble clic (encontrado en S3):** el segundo clic de un doble clic sobre el botón caía en el diálogo recién abierto y lo aceptaba sin leer (o lo cerraba). `ForgeConfirm` ignora los clics con `detail` ≥ 2; una ventana de tiempo frenaba también clics normales rápidos. E2E: `generation-guard` («doble click … pregunta una vez»).
- **Guardado antes de escribir:** se usa `ForgeAsistente.flushAll` (ya existía) en vez de una global nueva; solo dentro de `[data-asistente]` (con hx-boost queda la de una página anterior).
- `startGeneration` (servicio del front) quedó sin uso y se borró: ningún camino del servidor lanza la escritura.
