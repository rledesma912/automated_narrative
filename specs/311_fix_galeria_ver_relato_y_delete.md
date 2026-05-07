# Spec-311: Fix Galería — "Ver Relato" vacío y acción "Eliminar historia" ausente

## Metadata

| Campo | Valor |
|---|---|
| **Status** | In Progress |
| **Tipo** | Bugfix UI/UX + wiring frontend/backend |
| **Slice base** | S0 |
| **Fecha** | 2026-05-05 |
| **Owner** | Frontend + Presentation |
| **Depende de** | Spec-302 cerrado |

---

## 1. Objetivo

Corregir dos regresiones en la galería:

1. El CTA **"Ver Relato"** lleva a una vista sin contenido útil aunque existe relato persistido.
2. La card de historia en galería no expone la acción **"Eliminar historia"**, pese a existir backend para borrado.

---

## 2. Hallazgos actuales

### 2.1 "Ver Relato" apunta a flujo posiblemente incorrecto

- En galería, el link actual es:
  - `frontend/src/views/gallery.ejs` → `/historia/:storyId/relatos`
- Ese flujo renderiza `relatos.ejs` usando `getRelatosForStory()`:
  - `frontend/src/controllers/relatos.controller.ts`
  - `frontend/src/services/story.service.ts` → `GET /api/v1/story-templates/{id}/narratives`

Esto depende de que existan registros en `generated_narrative`.

### 2.2 Flujo "ver markdown" quedó desalineado

- Existe handler para ver markdown:
  - `frontend/src/controllers/historia.controller.ts` (`verMarkdownHandler`)
- Pero:
  - no está wireado en `frontend/src/routes/index.ts`
  - la vista `frontend/src/views/visualizar_markdown.ejs` no existe en el árbol actual

Conclusión: el producto quedó partido entre dos conceptos de "relato":
- relato exportado markdown de la historia (`story.file_path`)
- relatos alternativos (`generated_narrative`)

### 2.3 Eliminar historia: backend presente, CTA ausente

- Backend/API sí soporta hard delete:
  - `src/presentation/routers/story_router.py` (`DELETE /stories/{story_id}`)
- Frontend también tiene handler:
  - `frontend/src/controllers/historia.controller.ts` (`deleteStoryHandler`)
  - ruta interna: `DELETE /internal/historia/:storyId`
  - modal de confirmación: `/modales/confirmar-borrar/:storyId`
- En `gallery.ejs` no se renderiza botón/acción de borrar.

---

## 3. Decisión de producto cerrada

**Semántica oficial de "Ver Relato":**
- Debe abrir la vista de **relatos generados** (`generated_narrative`) de una historia.
- Esa vista debe incluir un **menú superior** para switchear entre las distintas versiones
  de relato generadas por NarrativeForge para la misma historia.
- Debe renderizarse como **partial** dentro del layout general existente, preservando:
  - sidebar izquierda
  - footer global

**Consecuencia:**
- No se usará este CTA para `file_path` markdown principal.
- El flujo markdown queda como acción separada (si se conserva en detalle de historia).

---

## 4. Scope

### In Scope

- Corregir CTA "Ver Relato" para que abra contenido real y no vacío.
- Restituir acción "Eliminar historia" en card de galería.
- Verificar wiring frontend/backend de ambas acciones.
- Tests unitarios/integración de routing/controladores de frontend para evitar regresión.

### Out of Scope

- Cambios de dominio de generación LLM.
- Rediseño visual completo de galería.
- Cambios en esquema de DB.

---

## 5. Diseño aprobado

1. Mantener navegación de galería a `/historia/:id/relatos`.
2. Reescribir la vista de relatos como partial compatible con `renderPage`:
   - contenido central en `relatos.ejs`,
   - sin romper sidebar/footer del layout base.
3. Agregar menú superior de selección de relato (tabs/lista horizontal):
   - una entrada por `generated_narrative`,
   - selección por defecto del relato más reciente,
   - cambio de relato sin salir de la página.
4. Estado vacío explícito:
   - si no hay relatos, mostrar mensaje claro y CTA de generación desde la historia.
5. Mantener acciones markdown fuera de este flujo (no mezclar responsabilidades).

---

## 6. Slices

### Slice S0 — Reproducción y baseline

- [x] S0-T1: reproducir desde galería el flujo "Ver Relato" en historia con contenido persistido.
- [x] S0-T2: confirmar ausencia de acción borrar en card.
- [x] S0-T3: snapshot `make lint` + `make test`.

### Slice S1 — Fix "Ver Relato"

- [x] S1-T1: corregir route/controller/view de `/historia/:id/relatos` para render no vacío.
- [x] S1-T2: implementar menú superior para switchear entre relatos generados.
- [x] S1-T3: asegurar render como partial dentro de layout general (sidebar + footer intactos).
- [x] S1-T4: validar estado vacío útil (sin pantalla muerta) cuando `relatos.length === 0`.

### Slice S2 — Restituir "Eliminar historia" en galería

- [x] S2-T1: agregar CTA en card (preferentemente con modal confirmación HTMX).
- [x] S2-T2: conectar a `/modales/confirmar-borrar/:storyId` y `DELETE /internal/historia/:storyId`.
- [x] S2-T3: confirmar redirección/refresh de galería tras delete.

### Slice S3 — Pruebas y hardening

- [x] S3-T1: tests frontend de controlador/ruta para "Ver Relato".
- [x] S3-T2: test de acción delete en galería.
- [x] S3-T3: `make lint` + `make test` verdes.

---

## 7. Criterios de aceptación

1. Desde galería, "Ver Relato" abre la vista de relatos generados de esa historia.
2. La vista muestra un menú superior para switchear entre versiones de relato.
3. La vista mantiene layout general (sidebar izquierda + footer).
4. Si no hay relatos, la UI muestra estado vacío accionable y no pantalla muerta.
5. Cada card de galería ofrece "Eliminar historia" y el borrado funciona extremo a extremo.
6. No se rompe edición/regeneración ni navegación actual.
7. Suite y lint verdes.

---

## 8. Riesgos

- Ambigüedad de producto entre "relato principal" y "relatos alternativos".
- Posibles rutas huérfanas por refactors previos (`verMarkdownHandler` sin route).
- UX inconsistente si conviven dos CTAs con naming similar ("Ver Relato" vs "Ver Relatos").

---

## 9. Nota de implementación

No mezclar semánticas de "relato principal markdown" con "relatos generados". El CTA
de galería queda asociado a `generated_narrative`.

## 10. Avance implementado (2026-05-05)

- `frontend/src/views/relatos.ejs`
  - reemplazada lógica rota de panel lateral por switcher superior por relato.
  - cada relato renderiza su panel de contenido y el cambio entre tabs ocurre en cliente sin recarga.
  - estado vacío explícito si no hay narrativas.
- `frontend/src/views/gallery.ejs`
  - se restituyó CTA `Eliminar` en cada card (cuando no está en `processing`).
  - integrado con modal HTMX (`/modales/confirmar-borrar/:storyId`) y delete interno existente.
- Verificación:
  - `make lint`: OK
  - `make test`: OK (497 passed)
  - `frontend npm test`: OK (15 passed)
