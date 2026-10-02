# SPEC-630: UI y bugs — segundo recorrido

**Fecha:** 2026-10-02
**Tipo:** SDD — mejoras de UI y corrección de bugs
**Estado:** SPECIFY — B1 descripto; se suman los hallazgos de la lista que trae el usuario
**Rama:** `feat/spec-630-ui-y-bugs` (desde `development`, `453cccb`)
**Extiende:** Spec-530 (asistente), Spec-550 (recorrido de la UI), Spec-580 (tono del sitio).

---

## ASSUMPTIONS

1. Mismo formato que la Spec-550: cada hallazgo entra como **B<n>** con lo que pasa hoy, la decisión (o las opciones, si falta decidir) y cómo se verifica. Las decisiones se toman de a grupos, con recomendación.
2. Datos descartables (2026-09-27): si algún hallazgo toca el esquema, se recrea la DB (`make dev-db`), sin migraciones.
3. El tono visible sigue la Spec-580 (voseo, sin jerga: `sin-jerga.view.test.ts`) y la gramática visual de la Spec-550 H9.
4. Cada checkpoint cierra con tests en verde y dev actualizado (`make dev-status`), con la URL de `storymaker.test` para validar.

---

## OBJECTIVE

Juntar en una spec los arreglos chicos de UI y los bugs que el usuario encuentra recorriendo dev, para implementarlos en slices cortos y llevarlos juntos a prod.

---

## 1. HALLAZGOS

### B1 — «Editar» no lleva siempre al mismo paso · **decidido**

**Qué pasa hoy (medido 2026-10-02):** según desde dónde se entra a editar una historia, se cae en un paso distinto del asistente, y eso confunde:

| Entrada | Archivo | Hoy cae en |
|---|---|---|
| «Editar» en Mis historias (galería) | `frontend/src/views/gallery.ejs:61` | 1 · Tu idea (`/direccion`) |
| «Editar» en la ficha de la historia | `frontend/src/views/historia.ejs:134` | 3 · Los actos (`/escaleta`) |
| Ruta vieja `/generar/cargar/:id` (redirección 301) | `frontend/src/routes/index.ts:26` | 1 · Tu idea (`/direccion`) |

**Decisión:** editar una historia existente **siempre** abre el paso **«3 · Los actos»** (`/asistente/{id}/escaleta`). Desde ahí los pasos de la barra (`_cabecera.ejs`) llevan a «Tu idea» y «Preguntas».

**Fuera de alcance (no cambia):**
- «Nuevo relato» (`/nuevo`) sigue empezando en «Tu idea»: la historia todavía no existe.
- Los pasos de la barra del asistente y el salto al terminar un análisis de la IA (`asistente.js`, `destino`) siguen como están: son navegación dentro del asistente, no «entrar a editar».
- Una historia sin actos (p. ej. recién importada) ya tiene su estado vacío en la escaleta (`escaleta.ejs:47`, «armar los actos»); no se agrega lógica de «caer en otro paso si no hay actos».

**Cómo se verifica:**
- Un único lugar arma la URL de edición (helper en el frontend, p. ej. `editarHref(storyId)`), usado por la galería, la ficha y la redirección de `/generar/cargar/:id`; así no se vuelven a separar.
- Test de vista (Vitest): el «Editar» de la galería y el de la ficha apuntan a `/asistente/{id}/escaleta`.
- Test de ruta: `/generar/cargar/:id` redirige a `/asistente/{id}/escaleta`.
- E2E: desde Mis historias → «Editar» → URL `/asistente/{id}/escaleta$`, con «Los actos» como paso actual.

### B2… — *(pendientes: lista del usuario)*

---

## 2. DECISIONES

| # | Decisión | Fecha |
|---|---|---|
| D1 | B1: editar una historia existente abre siempre «3 · Los actos» (`/escaleta`), desde cualquier entrada | 2026-10-02 |

---

## 3. CRITERIOS DE ÉXITO

- [ ] B1: las tres entradas de edición llevan a `/asistente/{id}/escaleta`, armadas desde un solo helper.
- [ ] Tests en verde (`make lint`, `make test`, `cd frontend && npm test`, Playwright) y dev reflejando los cambios.

---

## 4. PLAN

*(Se arma cuando esté la lista completa de hallazgos, agrupando en slices.)*

## 5. TASKS

*(Después del OK del plan.)*
