# Spec 039 — Mantenimiento: Scripts BD, Tests y Diagrama UML

**Estado:** ESPECIFICADO  
**Fecha:** 2026-04-21  
**Relacionado con:** Spec-038 (arquitectura vigente), Spec-001 (SDD)

---

## Contexto

Tras la implementación completa de Spec-038 (anclajes narrativos, renombre `beat → macro_beat`,
nuevas tablas `narrative_anchors` / `scenario` / `narrative_journal`) quedaron tres áreas con
deuda técnica de mantenimiento menor que no requieren cambios funcionales:

1. Scripts de base de datos desactualizados.
2. Tests que cubren flujos reemplazados o ya no representativos.
3. Ausencia de un diagrama UML de colaboración de clases actualizado.

---

## Tarea 1 — Scripts de base de datos

### Problema

| Archivo | Problema |
|---|---|
| `scripts/sql/insert_story.sql` | Inserta en tabla `beat` (no existe desde Spec-038; fue renombrada a `macro_beat`). Además faltan columnas nuevas: `narrative_context`, `memory_snapshot`, `active_scenario_id`. |
| `scripts/bash/db_clean.sh` | Limpia la lista `['narrative_journal', 'beat', 'story']`; la tabla `beat` no existe. Debe ser `macro_beat`. |

### Solución

**`insert_story.sql`**
- Actualizar el `INSERT INTO beat` → `INSERT INTO macro_beat`.
- Agregar las columnas requeridas por el esquema actual: `narrative_context`, `memory_snapshot`, `active_scenario_id` (puede ser NULL en el seed de ejemplo).
- El story de ejemplo debe ser coherente con la historia que ya existe en la fixture (El Monte Prohibido), o neutralizarlo a un placeholder genérico limpio.
- Verificar que el `story_id` referenciado en los beats exista también en el `INSERT INTO story` del mismo archivo.

**`db_clean.sh`**
- Cambiar `'beat'` → `'macro_beat'` en la lista de tablas a limpiar.
- Auditar si el script limpia también `narrative_anchors` y `scenario`; si no, agregarlas al orden de borrado respetando las FK (borrar en orden: `narrative_journal → macro_beat → narrative_anchors → scenario → story`).

### Criterio de aceptación
- `./scripts/bash/init_db.sh && sqlite3 stories.db ".tables"` muestra las 5 tablas del esquema Spec-038.
- La inserción del SQL de seed no arroja error de FK ni de columna inexistente.
- `db_clean.sh` no arroja error de tabla inexistente.

---

## Tarea 2 — Limpieza de tests

### Diagnóstico

#### Tests a eliminar

| Archivo | Razón |
|---|---|
| `tests/unit/application/test_story_analyst.py` | Cubre el flujo viejo de Spec-023: `DirectorUseCase._analyze_story()` → texto `narrative_brief` + `execute()` → `StoryPlan`. Ese flujo fue reemplazado por `StoryAnalystService.extract_anchors()` → `NarrativeAnchors` (Spec-038). La cobertura funcional equivalente ya existe en `test_story_analyst_service.py`. |
| `tests/unit/application/test_create_story_plan.py` | Cubre `DirectorUseCase.execute()` → `StoryPlan` con `parse_beats` (flujo de planificación lineal pre-Spec-038). El pipeline vigente es `execute_full()` cubierto exhaustivamente por `test_slice6_pipeline.py`. |

#### Tests a conservar (no tocar)

| Archivo | Razón |
|---|---|
| `test_slice6_pipeline.py` | Cubre `execute_full()`, `MemoryJournalist.extract()`, `VozUseCase.narrate()` — arquitectura vigente Spec-038. El prefijo "Slice 6" es histórico pero el contenido es completamente válido. |
| `test_slice7_debug.py` | Cubre `DebugCollector` con `narrative_context` (no `context_strategy`). Válido y específico. El prefijo "Slice 7" es histórico. |
| `test_narrative_context_builder.py` | Cubre `build_narrative_context()`, `build_voz_user_prompt()`, `build_voice_system_compact()` — métodos activos en `PromptBuilder`. |
| `test_story_analyst_service.py` | Cubre `StoryAnalystService` (Spec-038). Reemplaza funcionalmente a `test_story_analyst.py`. |
| Todos los demás | No presentan obsolescencia detectada. |

#### Verificación previa a borrar

Antes de eliminar los dos archivos, confirmar que `DirectorUseCase.execute()` y `StoryPlan` no
son la única cobertura de código vivo. Criterio:
- Si `execute()` aún es llamado desde la CLI (`python -m src plan`), conservar el test pero moverlo
  a un archivo con nombre representativo, p.ej. `test_director_legacy_plan.py`.
- Si `execute()` ya no tiene caller activo fuera de los tests, también eliminar el método.

### Criterio de aceptación
- `pytest tests -v` pasa sin errores tras el borrado.
- La cobertura de `StoryAnalystService`, `DirectorUseCase.execute_full()`, `VozUseCase`, `MemoryJournalist`, `PromptBuilder` no decrece respecto al baseline actual.

---

## Tarea 3 — Diagrama UML de colaboración de clases

### Problema

No existe ningún diagrama de colaboración de clases en el repo. El único material visual es:
- `docs/estandar_diseno_arquitectural.md` — diagramas de flujo SDD (proceso), no de clases.
- `docs/narrativeGenAgent.jpg` — imagen binaria de origen desconocido.

El `CLAUDE.md` tiene un diagrama de secuencia de texto (ASCII) que cubre el *flujo de mensajes*
pero no la *estructura de dependencias entre clases*.

### Solución

Crear `docs/colaboracion_clases.md` con un diagrama Mermaid `classDiagram` que modele:

**Capas a cubrir:**
- **Domain:** `Story`, `MacroBeat`, `NarrativeAnchors`, `Scenario`, `NarrativeJournal` (modelos),
  `LLMProvider` (interfaz), `LLMResponse` (value object).
- **Application:** `DirectorUseCase`, `VozUseCase`, `StoryAnalystService`, `SynopsisBeatMapper`,
  `MemoryJournalist`, `PromptBuilder`, `DebugCollector`.
- **Infrastructure (adapters):** `OllamaAdapter`, `AnthropicAdapter`, `GeminiCLIAdapter`,
  `MockLLMAdapter`, `ResponseNormalizer`.
- **Infrastructure (repositories):** `SQLStoryRepository`, `SQLMacroBeatRepository`,
  `SQLNarrativeAnchorsRepository`, `SQLScenarioRepository`, `SQLNarrativeJournalRepository`.
- **Core:** `StoryRunner` (wires).
- **Presentation/CLI:** `FastAPI routers` y `CLI commands` (como cajas, sin detallar métodos).

**Relaciones a mostrar:**
- Implementación de interfaz (`LLMProvider` ← adapters).
- Composición/dependencia en constructores (quién recibe a quién por DI).
- Asociación dominio (Story 1→* MacroBeat, Story 1→1 NarrativeAnchors, etc.).

**Convenciones:**
- Usar el formato Mermaid `classDiagram` para poder renderizarlo en GitHub y VS Code.
- Agrupar por capa con comentarios (`%% Domain`, `%% Application`, etc.).
- No listar todos los métodos/atributos de cada clase — solo los que aportan semántica de
  colaboración (constructores con dependencias, métodos clave del contrato).
- El diagrama debe caber en pantalla sin hacer scroll horizontal — priorizar claridad sobre
  exhaustividad.

### Criterio de aceptación
- El archivo `docs/colaboracion_clases.md` existe y contiene un bloque Mermaid válido.
- El diagrama renderiza correctamente en GitHub (sin errores de sintaxis Mermaid).
- Están presentes los 4 adapters, los 5 servicios de aplicación, los 5 modelos de dominio y
  `StoryRunner`.
- Las relaciones de implementación de `LLMProvider` y las dependencias de `DirectorUseCase`
  (recibe `LLMProvider`, `PromptBuilder`, `VozUseCase`, `MemoryJournalist`) son visibles.

---

## Orden de implementación

```
T1 — Scripts BD      (independiente, bajo riesgo)
T3 — Diagrama UML    (independiente, sin riesgo de regresión)
T2 — Limpieza tests  (requiere verificar callers de execute() antes de borrar)
```

T1 y T3 son independientes y pueden hacerse en paralelo.
T2 requiere verificación de callers de `execute()` antes de proceder.

---

## No incluido en este spec

- Cambios funcionales a la lógica de negocio.
- Migración del método `execute()` (si se decide remover, es un spec propio).
- Agregar nuevos tests más allá de los existentes.
