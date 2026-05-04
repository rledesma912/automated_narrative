# Spec-215: Regeneración Advertida de Historias Completadas

## Estado
APROBADO — pendiente de implementación

## Problema

Cuando una historia está en estado `completed`:
1. El botón "Regenerar" en `gallery.ejs` e `historia.ejs` dispara la regeneración **sin advertencia**, lo que puede causar pérdida accidental de contenido generado.
2. En `streaming-room.ejs` el botón "Regenerar" **no aparece** para historias completadas (solo para `failed`).
3. El archivo Markdown exportado **queda como huérfano en disco** al regenerar — se genera un nuevo archivo sin eliminar el anterior.

## Solución

### Principio
La regeneración de una historia completada debe ser posible **con advertencia explícita**. El sistema muestra un modal de confirmación que informa que se perderá la generación actual y el archivo Markdown. El usuario decide.

### Comportamiento final esperado

| Vista | Estado | Acción del botón |
|---|---|---|
| `gallery.ejs` | `completed` | Form POST directo (sin modal) |
| `gallery.ejs` | `failed`/`draft` | Form POST directo (sin cambios) |
| `historia.ejs` | `completed` | Form POST directo (sin modal) |
| `historia.ejs` | `failed`/`draft` | Form POST directo (sin cambios) |
| `streaming-room.ejs` | `completed` | Botón "Regenerar" que abre modal de advertencia |
| `streaming-room.ejs` | `failed` | Form POST directo (sin cambios) |

---

## Cambios requeridos

### Slice A — Backend: Limpieza de MD huérfano al regenerar

**Archivo:** `src/application/services/streaming_service.py` (líneas 50–58)

En `_main_producer()`, antes de `clear_story_artifacts()`, si la historia tiene `file_path`:
1. Calcular path físico: `Path("frontend/public") / story.file_path`
2. Borrar el archivo del disco con `path.unlink(missing_ok=True)`
3. Limpiar `file_path` en DB: `await story_repo.update_file_path(story.id, None)`

### Slice B — Frontend: Modal de confirmación para regenerar

**Archivo nuevo:** `frontend/src/views/partials/modal_regenerar.ejs`
- Icono de advertencia naranja (distinto al rojo de borrado)
- Mensaje: informa pérdida de generación actual y Markdown
- Botón "Cancelar": cierra modal (JS inline)
- Botón "Regenerar": `<form method="POST" action="/historia/<%= storyId %>/generar">` dentro del modal

**`frontend/src/controllers/historia.controller.ts`**
- Exportar nueva función `modalConfirmarRegenerar(req, res)`
- Renderiza `partials/modal_regenerar` con `{ storyId }` sin layout

**`frontend/src/routes/index.ts`**
- Agregar: `router.get("/modales/confirmar-regenerar/:storyId", modalConfirmarRegenerar)`

### Slice C — Frontend: Quitar modal de gallery.ejs e historia.ejs

**`frontend/src/views/gallery.ejs`** (líneas 61–67):
- Eliminar el botón HTMX con `hx-get="/modales/confirmar-regenerar/:storyId"` para status `completed`.
- Usar `<form method="POST">` directo para todos los estados (incluyendo `completed`).

**`frontend/src/views/historia.ejs`** (líneas 153–160):
- Eliminar el botón HTMX para status `completed`.
- Usar `<form method="POST">` directo para todos los estados.

### Slice D — Frontend: Botón "Regenerar" para completed en streaming-room.ejs

**`frontend/src/views/streaming-room.ejs`** (líneas 78–85):
- Añadir condición para `completed` con botón HTMX que abre modal
- Mantener el `<form>` existente para `failed` sin cambios

---

## Archivos modificados

| Archivo | Tipo de cambio |
|---|---|
| `src/application/services/streaming_service.py` | Limpieza de MD físico + DB antes de regenerar |
| `frontend/src/views/partials/modal_regenerar.ejs` | Modal de advertencia (usado solo en streaming-room) |
| `frontend/src/controllers/historia.controller.ts` | Handler `modalConfirmarRegenerar` (solo para streaming-room) |
| `frontend/src/routes/index.ts` | Ruta del modal (sin cambios) |
| `frontend/src/views/gallery.ejs` | Quitar modal - usar form POST directo |
| `frontend/src/views/historia.ejs` | Quitar modal - usar form POST directo |
| `frontend/src/views/streaming-room.ejs` | Botón "Regenerar" con modal para `completed` |

**No se modifican:**
- `story_router.py` — `_PATCHABLE_STATUSES` está correcto (valida destino, no origen)
- `story_repository.py` — `update_file_path` ya existe

---

## Notas técnicas

- El modal de regeneración usa `<form method="POST">` (no HTMX para la acción) para aprovechar el redirect que ya hace `generarDesdeHistoria`.
- El partial es distinto a `modal_confirm.ejs` porque este usa `hx-delete` — incompatible con el flujo de regeneración.
- El backend ya maneja correctamente el estado `completed` en `streaming_service.py:51-58` (limpia artefactos DB y continúa). Este spec solo añade limpieza del MD físico y la capa de UX.
