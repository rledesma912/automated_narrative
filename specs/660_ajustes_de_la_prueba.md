# SPEC-660: Ajustes de la prueba (escribir sin página intermedia, borrar personajes)

**Fecha:** 2026-10-10
**Tipo:** SDD — UI (frontend; el Core no cambia)
**Estado:** SPECIFY (camino B elegido por el usuario 2026-10-10; faltan maquetas y OK)
**Rama:** a definir (después de cerrar la Spec-650, o encima de su rama si las usuarias prueban todo junto)
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
- (Alternativa a decidir con las maquetas: sacar el borrado de la tarjeta del acto y dejarlo en un solo lugar. Más cambio; solo si el tacho no alcanza.)

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

- B2: ¿alcanza con el tacho y el texto, o el borrado se va de la tarjeta del acto? Se decide con las maquetas.
