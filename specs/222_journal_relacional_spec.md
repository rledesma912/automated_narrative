# Spec-222: Journaling Relacional y Persistencia Histórica

## 1. Problema Actual
El sistema de memoria narrativa (Journal) sufre de dos problemas de diseño:
- **Sobrescritura:** La tabla `narrative_journal` tiene una restricción `UNIQUE(story_id)`, lo que causa que solo se guarde el estado del último beat generado, perdiendo el historial intermedio en formato relacional.
- **Duplicación Desnormalizada:** El historial se conserva actualmente como un JSON string en la columna `memory_snapshot` de la tabla `macro_beat`. Esto dificulta consultas SQL directas sobre la evolución de misterios o estados emocionales.

## 2. Objetivos
- **Normalización:** Consolidar el historial narrativo en una única tabla relacional.
- **Observabilidad:** Permitir el seguimiento de la evolución narrativa beat a beat mediante consultas SQL.
- **Limpieza de Deuda:** Eliminar campos redundantes y desnormalizados (`memory_snapshot`).

## 3. Diseño de la Solución

### 3.1. Esquema de Base de Datos
Se modificará la tabla `narrative_journal` para permitir múltiples entradas por historia:

```sql
-- Nueva estructura propuesta
CREATE TABLE narrative_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT NOT NULL,
    beat_number INTEGER NOT NULL,
    last_events TEXT DEFAULT '',
    unresolved_mysteries TEXT DEFAULT '',
    physical_emotional_state TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE,
    UNIQUE(story_id, beat_number)
);
```

### 3.2. Cambios en el Dominio y Repositorios
- **`NarrativeJournal` (Modelo):** Se mantiene igual, pero la capa de persistencia ahora gestiona la relación con el beat.
- **`StoryRepository.save_journal`:** Ahora requiere el `beat_number`.
- **`StoryRepository.get_journal`:** 
    - `get_journal(story_id, beat_number=None)`
    - Si `beat_number` es `None`, debe retornar el journal del último beat completado.
- **`BeatRepository`:** Se elimina el manejo de `memory_snapshot`.

### 3.3. Orquestación
- El `DirectorUseCase` y el `Orchestrator` pasarán explícitamente el `beat.number` al guardar el journal.

## 4. Plan de Migración y Limpieza
1.  **Migración de DB:**
    - Modificar `connection.py` para reflejar el nuevo esquema.
    - Debido a las limitaciones de SQLite para `ALTER TABLE`, se recomienda recrear la tabla si es necesario o manejar la migración de datos desde `memory_snapshot` si existen historias activas.
2.  **Eliminación de Código Muerto:**
    - Quitar `memory_snapshot` de `MacroBeat` (modelo).
    - Quitar `memory_snapshot` de `SQLBeatRepository`.
    - Simplificar `MemoryJournalist.extract`.

## 5. Checklist de Tareas
- [ ] **Infraestructura (DB):**
    - [ ] Modificar `src/infrastructure/database/connection.py` para actualizar esquema de `narrative_journal`.
    - [ ] Eliminar columna `memory_snapshot` de la tabla `macro_beat`.
- [ ] **Dominio:**
    - [ ] Eliminar campo `memory_snapshot` de `MacroBeat` en `src/domain/models.py`.
- [ ] **Persistencia:**
    - [ ] Actualizar `StoryRepository.save_journal` para aceptar `beat_number`.
    - [ ] Actualizar `StoryRepository.get_journal` para soportar búsqueda por beat o "último disponible".
    - [ ] Eliminar lógica de `memory_snapshot` en `SQLBeatRepository.save` y mapeadores.
- [ ] **Aplicación / Orquestación:**
    - [ ] Simplificar `MemoryJournalist.extract` (eliminar generación de snapshot JSON).
    - [ ] Actualizar `DirectorUseCase` para manejar el flujo sin snapshots manuales.
    - [ ] Actualizar `Orchestrator` para persistir el journal con el número de beat correcto.
- [ ] **Limpieza:**
    - [ ] Ejecutar `scripts/bash/db_clean.sh` para iniciar con esquema fresco (o script de migración).

## 6. Plan de Pruebas

### 6.1. Pruebas Unitarias
- **`TestStoryRepository`:** 
    - Verificar que `save_journal` guarda múltiples registros para distintos `beat_number`.
    - Verificar que `get_journal(story_id)` sin número devuelve el registro con el `beat_number` más alto.
    - Verificar que `get_journal(story_id, n)` devuelve el registro exacto.
- **`TestBeatRepository`:**
    - Verificar que el guardado y carga de beats ya no incluye (ni falla por) el campo `memory_snapshot`.

### 6.2. Pruebas de Integración
- **Flujo de Generación Completo:**
    - Ejecutar una historia de 3 beats.
    - Consultar la base de datos y verificar que existen exactamente 3 filas en `narrative_journal` para ese `story_id`.
    - Validar que el contenido de `last_events` en el Beat 3 es coherente con lo sucedido en el Beat 2.
- **Resiliencia (Resume):**
    - Detener una generación en el Beat 2.
    - Reiniciar desde historia existente.
    - Verificar que el `Orchestrator` recupera correctamente el journal del Beat 2 para alimentar el contexto del Beat 3.

## 7. Criterios de Aceptación
- La tabla `narrative_journal` contiene una fila por cada beat narrado de una historia.
- El pipeline de generación mantiene la coherencia (el Beat N recibe el journal del Beat N-1).
- No quedan rastros de `memory_snapshot` en la base de datos ni en el código.
- `make test` pasa exitosamente.
