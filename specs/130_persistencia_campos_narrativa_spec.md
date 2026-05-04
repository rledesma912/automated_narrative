# Spec 065 — Corregir persistencia de campos de narrativa

## Problema

Durante la revisión con `--hasta voz:1` se detectaron tres problemas de persistencia:

| Campo | Tabla | Estado | Causa |
|-------|-------|--------|-------|
| `narrative_anchors` | `narrative_anchors` | ❌ Vacío | No existe método para persistir |
| `technical_context` | `macro_beat` | ❌ NULL | Campo huérfano, nunca se asigna |
| `memory_snapshot` | `macro_beat` | ⚠️ Parcial | Solo se persiste después de journal |

El campo `narrative_context` funciona correctamente.

---

## Decisión de diseño

### 1. Persistir `narrative_anchors`

Agregar método `save_narrative_anchors()` en `StoryRepository`:

```python
async def save_narrative_anchors(self, story_id: UUID, anchors: NarrativeAnchors) -> None:
    """Persiste los anclajes narrativos extraídos por el Analista."""
    conn = await get_connection()
    await conn.execute(
        """INSERT OR REPLACE INTO narrative_anchors
        (story_id, initial_state, threat_nature, horror_peak, spatial_anchor, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            str(story_id),
            anchors.initial_state,
            anchors.threat_nature,
            anchors.horror_peak,
            anchors.spatial_anchor,
            datetime.now().isoformat(),
        ),
    )
    await conn.commit()
    await conn.close()
```

Llamar desde `DirectorUseCase` después de extraer anclajes (línea 158).

### 2. Eliminar `technical_context`

El campo `technical_context` en `MacroBeat` es huérfano:
- Existe en el modelo (`domain/models.py:77`)
- Existe en la DB (`macro_beat.technical_context`)
- **Nunca se asigna** en ningún lugar del código

**Acción**: Eliminar el campo del modelo y de la DB para eliminar deuda técnica.

### 3. Persistir `memory_snapshot` antes del checkpoint (OBSOLETO - Ver Spec-222)

> **Nota:** El campo `memory_snapshot` ha sido eliminado en el **Spec-222**. La persistencia de la memoria narrativa ahora se realiza de forma relacional en la tabla `narrative_journal` por beat, eliminando la necesidad de snapshots en la tabla de beats.

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/database/repositories/story_repository.py` | Agregar `save_narrative_anchors()` |
| `src/application/use_cases/director_use_case.py` | Llamar `save_narrative_anchors()` después de `extract_anchors()` |
| `src/domain/models.py` | Eliminar `technical_context` de `MacroBeat` |
| `src/infrastructure/database/repositories/beat_repository.py` | Eliminar `technical_context` de save/get |

## Archivos a NO tocar

- Ningún cambio en la UI o CLI
- Las APIs de use cases permanecen igual
- Tests existentes no deben romperse

---

## Plan de slices

```
Slice A — Persistir narrative_anchors
          + story_repository.save_narrative_anchors()
          + director_use_case llama al método

Slice B — Eliminar technical_context
          + Quitar de domain/models.py
          + Quitar de beat_repository.py
          + Quitar de tabla DB (ALTER TABLE DROP COLUMN)

Slice C — Corregir memory_snapshot timing
          + Asignar antes del yield en voz checkpoint

Slice D — lint + test completo
```

---

## Testing

| Test | Qué verifica |
|------|--------------|
| `test_narrative_anchors_persisted` | Após `execute_full()`, los anchors existen en DB |
| `test_no_technical_context_column` | La columna no existe en macro_beat |
| `test_memory_snapshot_in_voz_checkpoint` | Con `stop_after=voz:1`, el beat tiene memory_snapshot |

---

## Success Criteria

1. `narrative_anchors` tiene registros en DB después de cualquier generación
2. `technical_context` eliminado del modelo y DB
3. `memory_snapshot` persiste incluso con `--hasta voz:1`
4. `make test` pasa
5. `make lint` pasa