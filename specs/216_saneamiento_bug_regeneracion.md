# SPEC-216: Saneamiento y Fix del Bug de Regeneración
## Estado
APROBADO (tras iteración — todas las preguntas respondidas)

---
## Problema
| # | Problema | Gravedad |
|---|---------|----------|
| 1 | `PATCH /stories/:id/status` rechaza estado `processing` (422) — no está en `_PATCHABLE_STATUSES` | CRITICA |
| 2 | Modal usa `hx-post` → navegación ambigua → se atasca antes de llegar a la Sala de Generación | CRITICA |
| 3 | Limpieza de beats/journal delegadas solo al inicio del stream SSE — si no se inicia stream, datos viejos persisten | MEDIA |
| 4 | `update_status` en `SQLStoryRepository` no cierra conexión SQLite → fuga de conexiones | MEDIA |

---
## Decisiones de Diseño Confirmadas

| # | Decision | Fuente |
|---|---------|--------|
| D1 | Si falla eliminación de archivo físico → **continue + log warning** (no rollback) | Patrón existente en `delete_story` (`story_router. py:240-244`): solo loguea si el archivo existía |
| D2 | Usar `observability.record(…)` para logging | Ya usado en todo el router, singleton en `observability_service.py` |
| D3 | Scope Slice B: solo `update_`status`, no auditar otros métodos | Confirmado: solo este método tiene fuga, los demás ya tienen `close()` |
| D4 | Controller `generarDesdeHistoria` existe y funciona correctamente | `historia.controller. ts:242-261` — llama PATCH processing + redirect a `/generar/stream/:id` |
| D5 | Sin riesgo de doble limpieza | Limpieza en endpoint es inmediata, limpieza en streaming es redundante. Ambas idempotentes. |

---
## Solucion — 4 Slices

### Slice A — Fix endpoint status + limpieza inmediata
**Archivo:** `src/presentation/routers/story_`router. py`

1.  Agregar `"processing"` a `_PATCHABLE_STATUSES` (línea 134)
2.  En `update_story_status`, detectar cuando `new_status == "processing"`:
    1.  Obtener el `story` completo para tener `file_path`
    2.  Si `story.file_path` existe:
        a.  Verificar que el archivo físico existe en `frontend/public/{file_path}`
        b.  Si existe → eliminarlo con `unlink()`
        c.  Loguear con `observability.record("system", f"Archivo físico eliminado: {file_path}", ...)`
    3.  Llamar `repo.update_file_path(story.id, None)` → limpiar `file_path` en DB
    4.  Llamar `repo.clear_story_artifacts(story.id)` → elimina beats + journal + anchors
    5.  `await repo.update_status(story.id, "processing")` → transición final
    6.  `observability.record("generation", f"Limpieza completa para regeneración — story_id={story_ id}", ...)`
**Nota:** El orden es importante: primero limpiar artefactos y archivos, después hacer el UPDATE de status. Si falla algo del archivo físico, se continúa (patrón D1).

---
### Slice B — Fix fuga de conexiones
**Archivo:** `src/infrastructure/database/repositories/story_repository. py`
1.  En `update_status` (línea 165-173): agregar `await conn.close()` al final del método (después de `commit()`)

---
### Slice C — Fix navegacion del modal
**Archivo:** `frontend/src/views/partials/modal_regenerar. ejs`
1.  Reemplazar el `<button hx-post>` (líneas 29-35) por:
    ```html
    <form method="POST" action="/historia/<%= storyId %>/generar">
      <button type="submit"
              class="flex items-center gap-2 px-6 py-2 bg-forge-accent ...">
        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
        Regenerar
      </button>
    </form>
    ```
2.  El `hx-target` y `hx-swap` ya no son necesarios — el controller maneja la redirección

---
### Slice D — Documentar red de seguridad en streaming (sin cambios de codigo)
**Archivo:** `src/application/services/streaming_service. py`

1.  Agregar comentario en `_main_producer` o donde esté la lógica de limpieza:
    ```python
    # Salvaguarda redundante: esta limpieza es segura porque la limpieza
    # real ocurre en update_story_status cuando se confirma la regeneración.
    # Ambas son idempotentes — sin riesgo de doble limpieza.
    ```

---
## Criterios de Aceptacion

| # | Criterio | Forma de verificar |
|---|----------|----------------|
| CA1 | Al confirmar regeneración, navegador redirige a `/generar/stream/:id` | Test e2e manual |
| CA2 | Archivo Markdown eliminado de `frontend/public/output_stories/` **antes** de iniciar stream | Test: mock filesystem, verificar `unlink()` fue llamado |
| CA3 | Beats previos eliminados de tabla `macro_beat` | Test: verificar `repo.clear_story_artifacts` fue llamada |
| CA4 | Estado de historia en DB es `processing` | Test: verificar query en DB |
| CA5 | No hay conexiones SQLite abiertas tras la operacion | Test: verificar `conn.close()` fue llamado en `update_status` |
| CA6 | El modal no usa `hx-post` | Inspección del template |

---
## Archivos a modificar (resumen)

| Archivo | Cambio | Linea aprox |
|---------|--------|------------|
| `src/presentation/routers/story_`router. py` | Slice A | 134 + nuevo bloque if |
| `src/infrastructure/database/repositories/story_repository. py` | Slice B | ~173 |
| `frontend/src/views/partials/modal_regenerar. ejs` | Slice C | 29-35 |
| `src/application/services/streaming_service. py` | Slice D (comentario) | — |

---
## Testing

| Test | Tipo | Archivo |
|------|------|---------|
| `test_update_status_adds_processing` | Unitario | `tests/unit/` |
| `test_regeneration_cleans_artifacts` | Unitario | `tests/unit/` |
| `test_regeneration_deletes_md_file` | Unitario (mock filesystem) | `tests/unit/` |
| `test_update_status_closes_connection` | Unitario (mock conn) | `tests/unit/` |
| `test_regeneration_modal_uses_form_post` | Integración | Inspección visual |