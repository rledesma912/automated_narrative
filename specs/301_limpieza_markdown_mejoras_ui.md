# Spec-301: Limpieza de Funcionalidad Markdown y Mejoras UI

## Metadata

| Campo | Valor |
|-------|-------|
| **Status** | Draft |
| **Tipo** | Refactor / Cleanup |
| ** slice** | S0 - Preparación y Validación |
| **Fecha** | 2026-05-05 |
| **Owner** | Backend / Frontend |

---

## 1. Objetivos (Objectives)

### Objetivo Principal

Limpiar el codebase eliminando completamente la funcionalidad legacy de exportación a markdown que ya no se utiliza, manteniendo únicamente la funcionalidad de "relatos" (GeneratedNarratives).

### Objetivos Específicos

1. **Eliminar funcionalidad markdown legacy**: Remover todo el código relacionado con exportación a archivos .md en frontend y backend
2. **Corregir vista de relatos**: Agregar link de vuelta a galería y recuperar el sidebar lateral
3. **Limpiar temas**: Eliminar el tema "umbral" que no se usa
4. **Mantener estabilidad**: No introducir breaking changes en la generación de relatos ni en la galería

---

## 2. Contexto y Motivación (Context)

### Estado Actual

- Existe funcionalidad de exportar historias a archivos markdown en `frontend/public/output_stories/`
- Hay múltiples rutas y handlers en frontend para ver/descargar/exportar markdown
- El theme "umbral" está definido pero no se usa activamente
- La vista de relatos (nueva funcionalidad Spec-235) tiene dos problemas:
  - No tiene link para volver a la galería
  - No muestra el sidebar lateral

### Problema

La funcionalidad de markdown legacy:
- Añade complejidad sin valor (los relatos se ven en la UI)
- Requiere mantenimiento de archivos en disco
- Las rutas están deshabilitando el sistema y ocupan espacio en el código

### Beneficios Esperados

- Código más limpio y mantenible
- UI de relatos completamente funcional
- Temas精简 (solo los 3 que se usan)

---

## 3. Scope

### In Scope

**Frontend:**
- Eliminar carpeta `frontend/public/output_stories/`
- Eliminar rutas de markdown en `routes/index.ts`
- Eliminar handlers de markdown en `historia.controller.ts`
- Eliminar vista `visualizar_markdown.ejs`
- Actualizar `gallery.ejs` (quitar referencias a markdown)
- Eliminar theme "umbral" de `themes.json`
- Fix `relatos.ejs`: agregar link volver a galería
- Fix `relatos.controller.ts`: pasar activePage para sidebar

**Backend:**
- Eliminar `src/infrastructure/renderers/markdown_renderer.py`
- Eliminar `src/infrastructure/parsers/markdown_parser.py`

**Tests:**
- Eliminar `tests/unit/infrastructure/test_markdown_parser.py`
- Eliminar `tests/unit/infrastructure/test_markdown_renderer.py`

### Out of Scope

- Modificar funcionalidad de generación de relatos (GeneratedNarratives)
- Cambiar el flujo de creación de historias
- Modificar la base de datos (file_path en stories se mantiene por compatibilidad)

---

## 4. Cambios Detallados (Changes)

### Slice S0: Preparación y Validación

**Objetivo:** Validar estado actual antes de hacer cambios

- [ ] Verificar que la API está corriendo (health check)
- [ ] Verificar que el frontend compila correctamente
- [ ] Documentar rutas actuales de markdown
- [ ] Identificar dependencias del código a eliminar

### Slice S1: Limpieza Frontend - Rutas y Handlers

**Objetivo:** Eliminar código de markdown del frontend sin romper build

1. **Eliminar rutas de markdown** (`routes/index.ts`):
   - `verMarkdownHandler`
   - `downloadMarkdownHandler`
   - `exportStoryHandler`
   - `deleteMarkdownHandler`
   - `markdownCheckHandler`
   - `confirmDeleteMarkdownModal`

2. **Eliminar handlers de markdown** (`historia.controller.ts`):
   - Las funciones listadas arriba

3. **Eliminar vista** (`visualizar_markdown.ejs`):
   - Archivo completo

4. **Actualizar gallery.ejs**:
   - Quitar bloque `<span hx-get="/internal/historia/...markdown-check">`
   - Quitar botón "Exportar"

**Verificación:** `npm run build` pasa sin errores

### Slice S2: Limpieza Backend

**Objetivo:** Eliminar archivos de render/parse markdown del backend

1. **Eliminar archivos**:
   - `src/infrastructure/renderers/markdown_renderer.py`
   - `src/infrastructure/parsers/markdown_parser.py`

2. **Eliminar tests**:
   - `tests/unit/infrastructure/test_markdown_parser.py`
   - `tests/unit/infrastructure/test_markdown_renderer.py`

**Verificación:** `make test` pasa (sin los tests eliminados)

### Slice S3: Limpieza de Archivos Estáticos

**Objetivo:** Eliminar carpeta de outputs markdown

1. **Eliminar carpeta**: `frontend/public/output_stories/`
   - Todos los archivos .md generados

**Verificación:** Carpeta no existe

### Slice S4: Theme Cleanup

**Objetivo:** Eliminar theme no usado

1. **Eliminar theme "umbral"** (`themes.json`)
   - Quedan: horror, noir, light-contrast

**Verificación:** themes.json solo tiene 3 temas

### Slice S5: Fix UI - Relatos

**Objetivo:** Corregir problemas en la vista de relatos

1. **Agregar link volver a galería** (`relatos.ejs`)
   - Agregar link "← Volver a Galería" al inicio

2. **Fix sidebar** (`relatos.controller.ts`)
   - Agregar `activePage: 'gallery'` al render

**Verificación:**
- Link visible en página de relatos
- Sidebar aparece y navegación funciona
- `npm run build` pasa

---

## 5. Tests

### Tests de Integración (Post-Implementación)

| Test | Descripción | Criterio |
|------|-------------|----------|
| Build Frontend | `cd frontend && npm run build` | Pasa sin errores |
| Health API | `curl http://localhost:8010/api/v1/health` | {"status":"healthy"} |
| Galería | `curl http://localhost:3000/galeria` | HTML con historias |
| Ver Relatos | `curl http://localhost:3000/historia/{id}/relatos` | HTML con sidebar |
| Theme Switch | POST /theme con tema diferente | Tema cambia |

### Tests de Regresión

- Galería muestra todas las historias correctamente
- Link "Ver Relato" en galería funciona
- Generación de nuevos relatos funciona
- Botón "Copiar Relato" funciona

---

## 6. Checklist de Tareas (Task Checklist)

### Slice S0 - Preparación

- [ ] S0-T1: Verificar estado actual (API health, build)
- [ ] S0-T2: Documentar rutas de markdown a eliminar

### Slice S1 - Frontend Routes/Handlers

- [ ] S1-T1: Eliminar imports de handlers de markdown en routes/index.ts
- [ ] S1-T2: Eliminar rutas de markdown en routes/index.ts
- [ ] S1-T3: Eliminar funciones de markdown en historia.controller.ts
- [ ] S1-T4: Eliminar visualizar_markdown.ejs
- [ ] S1-T5: Actualizar gallery.ejs (quitar markdown-check y exportar)
- [ ] S1-T6: Verificar build pasa

### Slice S2 - Backend Cleanup

- [ ] S2-T1: Eliminar markdown_renderer.py
- [ ] S2-T2: Eliminar markdown_parser.py
- [ ] S2-T3: Eliminar test_markdown_parser.py
- [ ] S2-T4: Eliminar test_markdown_renderer.py
- [ ] S2-T5: Verificar tests pasan

### Slice S3 - Archivos Estáticos

- [ ] S3-T1: Eliminar carpeta output_stories

### Slice S4 - Theme Cleanup

- [ ] S4-T1: Eliminar theme "umbral" de themes.json

### Slice S5 - Fix UI Relatos

- [ ] S5-T1: Agregar link volver a galería en relatos.ejs
- [ ] S5-T2: Agregar activePage en relatos.controller.ts
- [ ] S5-T3: Verificar build pasa
- [ ] S5-T4: Test manual de navegación

---

## 7. Consideraciones de Breaking Changes

### Posibles Breaking Changes

1. **Rutas eliminadas**: Si hay clientes externos usando `/historia/:id/ver-markdown` o `/historia/:id/descargar-markdown`, dejarán de funcionar
   - **Mitigación**: Solo afecta frontend interno, no hay clientes externos documentados

2. **Tests eliminados**: Coverage baja ligeramente
   - **Mitigación**: Son tests de funcionalidad eliminada

3. **Theme "umbral"**: Si algún usuario lo tiene seleccionado en cookie, volverá a "horror"
   - **Mitigación**: Solo afecta si alguien tinha "umbral" activo

### Slice Strategy para Evitar Breaking Changes

1. **Orden de implementación**: S0 → S1 → S2 → S3 → S4 → S5
2. **Verificación entre slices**: Build pasa antes de avanzar
3. **No modificar funcionalidad activa**: Solo limpiar código legacy

---

## 8. Commands de Verificación

```bash
# Verificar estado actual
cd frontend && npm run build
curl http://localhost:8010/api/v1/health
curl http://localhost:3000/galeria

# Post-cambios
cd frontend && npm run build
make test
```

---

## 9. Notes

- La funcionalidad de "relatos" (GeneratedNarratives) NO se toca - solo se limpia el markdown legacy
- El campo `file_path` en la tabla stories se mantiene por compatibilidad hacia atrás
- Los temas disponibles después del cambio: horror, noir, light-contrast
- La vista de relatos usa la API de GeneratedNarratives, no los archivos markdown

---

## 9.1 Bugs Detectados y Correcciones

### Bug-301-01: Link de generar/regenerar eliminado inadvertidamente

**Descripción:** Al limpiar el bloque de markdown-check en gallery.ejs, se eliminó incorrectamente el bloque de botones para generar/regenerar historias.

**Síntoma:** En las cards de historias en la galería, no aparecía el botón "Generar" para historias en estado draft ni "Regenerar" para historias completadas.

**Causa:** El bloque de código que contenía los forms de generar/regenerar estaba junto al bloque de markdown-check que se eliminó.

**Corrección applied:** Se restauró el código de generar/regenerar en `gallery.ejs`:
- Para historias en estado 'completed': botón "Regenerar" (icono refresh-cw)
- Para historias en estado 'draft' o 'failed': botón "Generar" o "Reintentar" (icono zap)
- Para historias en estado 'processing': no se muestra ningún botón (ya estaba correcto)

**Archivo modificado:** `frontend/src/views/gallery.ejs`

**Fecha de detección:** 2026-05-05
**Fecha de corrección:** 2026-05-05
**Estado:** Corregido ✓

### Bug-301-02: Spinner desaparece inmediatamente en regeneración

**Descripción:** Al hacer click en "Iniciar Regeneración" en la sala de creación, el spinner de carga aparece brevemente y luego desaparece antes de que el LLM termine de procesar.

**Síntoma:** El div `initial-spinner` con el mensaje "El LLM está procesando tu historia" aparece un instante y luego se oculta.

**Causa:** La función `hideSpinner()` se ejecutaba en el primer evento `status` del EventSource (SSE), que se emite inmediatamente al conectarse, ocultando el spinner antes de que真正开始 el procesamiento.

**Corrección applied:** Se eliminó la llamada a `hideSpinner()` del evento `status` en `streaming-room.ejs`. El spinner ahora solo se oculta cuando llega el evento `beat_start` (cuando realmente comienza a generar contenido).

**Archivo modificado:** `frontend/src/views/streaming-room.ejs`

**Fecha de detección:** 2026-05-05
**Fecha de corrección:** 2026-05-05
**Estado:** Corregido ✓

### Bug-301-03: Vista de relatos no muestra contenido

**Descripción:** La página de relatos muestra la interfaz correcta pero no muestra el contenido del relato generado.

**Síntoma:** La página `/historia/{id}/relatos` carga correctamente con el sidebar y el layout, pero el área de contenido muestra "No hay relatos generados aún" o no muestra el contenido aunque exista un relato en la base de datos.

**Causa probable:** 
1. La API `/api/v1/story-templates/{id}/narratives` devuelve un array vacío
2. La tabla `generated_narrative` en la base de datos está vacía
3. Problema en el mapeo de datos entre el controlador y la vista

**Estado:** En investigación

**Archivos relacionados:**
- `frontend/src/controllers/relatos.controller.ts`
- `frontend/src/services/story.service.ts`
- `frontend/src/views/relatos.ejs`

### Bug-301-04: Error en CLI al completar generación - missing output_path

**Descripción:** Al ejecutar `python -m src generate` con el input YAML, el proceso de generación de beats culmina correctamente pero al final falla con error:

```
ProgressReporter.done() missing 1 required positional argument: 'output_path'
```

**Síntoma:** La generación de la historia falla al finalizar con este error.

**Causa:** En los cambios del spec-301 se eliminó la función `_write_markdown()` y las llamadas a `reporter.done()` que pasaban el `output_path`. Sin embargo, la firma del método `done()` en `ProgressReporter` requería el parámetro `output_path` como obligatorio.

**Corrección applied:** Se modificó `src/cli/progress.py` para hacer `output_path` opcional (`Path | None = None`) en ambas clases:
- `ProgressReporter.done()`
- `SilentReporter.done()`

**Archivos modificados:** `src/cli/progress.py`

**Fecha de detección:** 2026-05-05
**Fecha de corrección:** 2026-05-05
**Estado:** Corregido ✓

### Bug-301-05: Funcionalidad de generar relatos no estaba conectada

**Descripción:** El código para generar relatos (`generateNarrativeHandler`, endpoint `/api/v1/story-templates/{id}/generate-narrative`) existía pero:
- Faltaba la ruta en `routes/index.ts`
- No había botón en la UI para invocar la funcionalidad
- La tabla `generated_narrative` siempre estaba vacía porque nunca se llamaba al endpoint

**Síntoma:** Al completar una historia, la tabla `generated_narrative` queda vacía. La funcionalidad de relatos no funciona.

**Causa:** El handler `generateNarrativeHandler` existía pero no estaba registrado como ruta, y no había botón en la página de historia para generar el relato.

**Corrección applied:**
1. Se agregó la ruta `POST /historia/:storyId/generar-relato` en `frontend/src/routes/index.ts`
2. Se importó y registró `generateNarrativeHandler`
3. Se agregó botón "Generar Relato" y "Ver Relatos" en la página de historia (`historia.ejs`)

**Archivos modificados:**
- `frontend/src/routes/index.ts`
- `frontend/src/views/historia.ejs`

**Fecha de detección:** 2026-05-05
**Fecha de corrección:** 2026-05-05
**Estado:** Corregido ✓

---

## 10. Estado de Ejecución

| Slice | Estado | Notas |
|-------|--------|-------|
| S0 - Preparación | [x] | Build verificado |
| S1 - Frontend Routes | [x] | Rutas y handlers eliminados |
| S2 - Backend Cleanup | [x] | Archivos markdown y tests eliminados |
| S3 - Archivos Estáticos | [x] | output_stories eliminado |
| S4 - Theme Cleanup | [x] | Theme umbral eliminado |
| S5 - Fix UI Relatos | [x] | Link volver y sidebar añadidos |