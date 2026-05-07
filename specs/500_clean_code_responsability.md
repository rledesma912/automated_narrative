# Spec-500: Saneamiento de Responsabilidades — Clean Code en el Core (v2)

**Fecha de reconstrucción:** 7 de mayo de 2026
**Fecha de apertura original:** 6 de mayo de 2026
**Estado:** Living / Backlog
**Prioridad:** Variable (por slice)
**Metodología:** SDD, refactor incremental sin cambio de comportamiento — zero breaking changes entre slices

---

## 1. Objetivo

Spec **viva** que acumula smells de responsabilidad detectados en el código del core
(`src/core/`, `src/application/`) durante el desarrollo. No es un refactor único: es un
registro evolutivo. Cada smell se resuelve en un **slice independiente** cuando el
contexto lo permite, sin alterar el comportamiento observable del pipeline.

### Criterios de inclusión

- Violaciones claras de SRP (clase que orquesta + persiste + traduce).
- God objects (>300 líneas, >5 dependencias inyectadas, >3 responsabilidades distinguibles).
- Métodos largos (>80 líneas) que mezclan niveles de abstracción.
- Duplicación entre el pipeline CLI y el pipeline web/SSE.
- Dependencias creadas internamente que impiden testing unitario.

### Criterios de exclusión

- Smells ya cubiertos por specs vivas con plan propio (312, 150, 310).
- Code smells cosméticos sin impacto en mantenibilidad (naming menor, formato).
- Archivos largos por su naturaleza (templates EJS, YAML de prompts).
- Cambios de comportamiento funcional del pipeline LLM.

### Reglas del refactor

1. **Tests de caracterización primero.** Antes de extraer algo, asegurar que existe
   cobertura del comportamiento actual.
2. **Zero breaking changes por slice.** Cada slice mantiene la misma API pública que
   antes del cambio. Los call sites no se modifican a menos que sea estrictamente
   necesario para el slice.
3. **Un cambio lógico por slice.** No mezclar refactor con fix, ni refactor con feature.
4. **Documentar al cerrar.** Cuando un smell se resuelve,marcar el bloque y documentar
   qué se hizo en la sección de resultados.

---

## 2. Smells Detectados (Inventario)

### 2.1 `DirectorUseCase` — Loop monolítico con servicios internos

**Ubicación:** `src/application/use_cases/director_use_case.py` (320 líneas)

**Síntoma:**
- `execute_full()` (líneas 134-295) ejecuta las 3 fases globales + loop de 5 beats
  donde cada iteración: crea 4 servicios internamente, ejecuta 3 LLM calls, hace
  yield con 3 datos crudos, y tiene 5 branches de `stop_at` dispersos.
- `VozUseCase` y `MemoryJournalist` se crean internamente en `__init__` pero otros
  servicios (`StoryAnalystService`, `RuleScenarioResolverService`, `SynopsisBeatMapper`)
  se crean dentro de `execute_full()` en cada ejecución.
- Los callbacks `on_plan_ready`, `on_step_done`, `on_step_start` mezclan reporter CLI
  con la lógica del pipeline.

**Por qué es smell:**
- **Testing:** no se puede testear una fase individual sin mockear todo el loop.
- **Checkpoints:** la lógica de `stop_at` está entrelazada con el flujo — no hay forma
  de detener en un checkpoint sin ejecutar todo el bucle.
- **Servicios internos:** `StoryAnalystService` y `RuleScenarioResolverService` se
  instancian en cada llamada a `execute_full` — no hay inyección, no hay test unitario.

**Evidencia:**

| Check | Valor |
|---|---|
| `wc -l director_use_case.py` | 320 líneas |
| Servicios creados en `execute_full` | 3 (`StoryAnalystService`, `RuleScenarioResolverService`, `SynopsisBeatMapper`) |
| Branches `stop_at` | 5 (`analyst`, `mapper:N`, `voz:N`, `journal:N`) |
| Callbacks acoplados | 3 (`on_plan_ready`, `on_step_done`, `on_step_start`) |

**Smells derivados ya resueltos por Spec-312:**

| Item original | Estado |
|---|---|
| `FinalizeStoryUseCase` duplicado | **RESUELTO** — Spec-312 implementó `consolidate_and_save` canónico |
| `consolidate_and_save` en CLI y streaming | **RESUELTO** — `StoryRunner` y `stream_story` lo invocan |

---

### 2.2 `StoryRunner` — Duplicación de run_full / run_from_story

**Ubicación:** `src/core/orchestrator.py` (225 líneas)

**Síntoma:**
- `run_full()` (51-168) y `run_from_story()` (170-216) comparten ~60% del mismo código:
  crear `DirectorUseCase` → iterar beats con `async for` → guardar beat → guardar journal →
  consolidar.
- El `ProgressReporter` se inyecta como dependencia pero sus métodos (`step_start`,
  `step_done`, `beat_done`) están acoplados a la estructura del loop de CLI.
- 7 dependencias directas en el constructor.

**Por qué es smell:**
- Duplicación: cualquier cambio en el loop de beats requiere editar ambas funciones.
- El `async for ... director.execute_full()` / `director.execute_narration()` hace que
  `StoryRunner` conozca demasiado sobre el interior del Director.
- Si `DirectorUseCase` expone fases públicas (slice §3.1), `StoryRunner` podría delegar
  el loop a un use case dedicado.

**Evidencia:**

| Check | Valor |
|---|---|
| `wc -l orchestrator.py` | 225 líneas |
| Dependencias inyectadas | 7 (`llm`, `story_repo`, `beat_repo`, `prompt_builder`, `output_dir`, `reporter`, `debug_collector`) + 1 opcional (`narrative_use_case`) |
| Líneas duplicadas entre `run_full` y `run_from_story` | ~50 (estimado por estructura) |

---

### 2.3 Callbacks vs SSE — Dos mecanismos para el mismo evento

**Ubicación:** `src/application/use_cases/director_use_case.py` + `src/application/services/streaming_service.py`

**Síntoma:**
- `execute_full` yield `(beat, journal, elapsed)` — evento crudo del pipeline.
- `StoryRunner` consume esto y lo traduce a `reporter.step_start/step_done/beat_done`.
- `stream_story` consume lo mismo y lo traduce a `StreamEvent` (STATUS, BEAT_START,
  BEAT_DONE, HEARTBEAT, DONE).
- Si el pipeline agrega una nueva fase, hay que modificar 3 archivos.

**Por qué es smell:**
- La traducción de eventos está duplicada en CLI y SSE.
- `DirectorUseCase` no debería saber que existe un `ProgressReporter` ni un `StreamEvent`.
- Los callbacks en `execute_full` fueron diseñados solo para CLI — no hay abstracción
  de nivel de dominio.

---

### 2.4 Servicios internos en DirectorUseCase que impiden testing

**Ubicación:** `src/application/use_cases/director_use_case.py`

**Síntoma:**

```python
# Línea 163-165 — se crea en cada execute_full
analyst = StoryAnalystService(
    self.llm, self.prompt_builder, self.normalizer, self.debug_collector
)
```

```python
# Línea 182-184 — se crea en cada execute_full
resolver = RuleScenarioResolverService(
    self.llm, self.prompt_builder, self.normalizer, self.debug_collector
)
```

**Por qué es smell:**
- En cada ejecución se re-instancian los servicios. No hay forma de inyectar un mock
  en tests unitarios sin parchear internamente.
- Si `StoryAnalystService` cambia su firma, todos los tests que parchean directamente
  rompen.

---

## 3. Plan de Slices (Incremental, Quirúrgico)

> Cada slice se ejecuta con la disciplina de `incremental-implementation` skill:
> implement → test → verify → commit. Ningún slice altera la API pública existente.

---

### Slice S-A — PhaseEvent: abstracción de eventos del pipeline

**Objetivo:** Definir un DTO `PhaseEvent` que represente eventos de fase del pipeline.
No cambiar comportamiento — solo extraer una clase nueva.

**Cambio:** Agregar `src/domain/events.py` con `PhaseEvent` (Enum) y `PipelinePhaseData`
(Dataclass). Los eventos actuales: `PLAN_READY`, `ANALYST_DONE`, `BEAT_START`,
`BEAT_COMPLETE`, `JOURNAL_DONE`, `STEP_START`, `STEP_DONE`.

**Evidencia de avance:** Tests unitarios del nuevo módulo pasan. Ningún archivo
existente modificado.

---

### Slice S-B — Extraer fase global de `execute_full` → método público

**Depende de:** S-A

**Objetivo:** `execute_full` crea internamente `StoryAnalystService` y
`RuleScenarioResolverService`. Extraer la lógica de la **fase global**
(analyst + resolver → anclajes + distribución) a un método público
`prepare_story(story) -> (anchors, rule_distribution, num_beats)`.

**Cambio mínimo:**
1. Agregar método `prepare_story(story) -> dict` en `DirectorUseCase`.
2. `execute_full` delega la fase global a `prepare_story` internamente
   (sin cambiar la firma pública).
3. Agregar tests unitarios para `prepare_story`.

**Criterio de éxito:** Tests existentes de `DirectorUseCase` siguen verdes. Tests
nuevos para `prepare_story` pasan.

---

### Slice S-C — Extraer ejecución de un beat → método público

**Depende de:** S-B

**Objetivo:** El loop de beats en `execute_full` es una sola secuencia.
Extraer `_execute_single_beat(story, beat_id, anchors, journal) -> (beat, journal, elapsed)`.

**Cambio mínimo:**
1. Agregar método privado `_execute_single_beat` que ejecuta mapper + voz + journal
   para un beat.
2. El loop de `execute_full` llama a `_execute_single_beat` por cada beat.
3. Inyectar `StoryAnalystService`, `RuleScenarioResolverService`, `SynopsisBeatMapper`
   como dependencias opcionales del constructor (si no se pasan, se crean como hoy).

**Criterio de éxito:** `pytest tests/unit/application/use_cases/test_director_use_case.py`
pasa (regresión cero). Tests nuevos para `_execute_single_beat` pasan.

---

### Slice S-D — Reducir dependencias de StoryRunner (refactor mínimo)

**Depende de:** S-B, S-C

**Objetivo:** `run_full` y `run_from_story` duplican ~60% de la lógica de loop.
Extraer la lógica común a un método privado `_narrate_beats(story, beat_iterator)`.

**Cambio mínimo:**
1. Agregar `_narrate_beats(story, beats, initial_journal) -> list[Beat]` en `StoryRunner`.
2. `run_full` y `run_from_story` lo invocan. La lógica de guardar beat + journal + reporter
   queda centralizada.
3. Mantener todas las firmas existentes. Cero call sites modificados.

**Criterio de éxito:** Tests de `test_orchestrator.py` verdes. Ningún breaking change.

---

### Slice S-E — Adapter para reporter (decoupling)

**Depende de:** S-A

**Objetivo:** Eliminar el acoplamiento entre la estructura del loop de beats y el
`ProgressReporter`. Crear un `PipelineAdapter` que traduzca `PhaseEvent` →
llamadas a `ProgressReporter`.

**Cambio mínimo:**
1. Crear `src/core/adapters/progress_adapter.py` con interfaz `PipelineProgressListener`.
2. `StoryRunner` inyecta un adapter que implementa la interfaz (no sabe de `ProgressReporter`).
3. `ProgressReporter`implementa `PipelineProgressListener`.
4. `stream_story` usa su propio adapter hacia `StreamEvent`.

**Criterio de éxito:** `StoryRunner` ya no depende directamente de `ProgressReporter`.
Tests nuevos para el adapter. Tests existentes verdes.

---

### Slice S-F — Injección de servicios en DirectorUseCase (testing habilitación)

**Depende de:** S-B, S-C

**Objetivo:** Permitir que `StoryAnalystService`, `RuleScenarioResolverService` y
`SynopsisBeatMapper` se inyecten como dependencias opcionales del constructor.

**Cambio mínimo:**
1. Agregar parámetros opcionales al constructor: `analyst_service`, `resolver_service`,
   `beat_mapper`.
2. Si no se pasan, se crean internamente (comportamiento actual).
3. Si se pasan, se usan (nuevo — habilita tests con mocks).
4. Tests unitarios existentes y nuevos siguen verdes.

**Criterio de éxito:** Se puede instanciar `DirectorUseCase` con mocks de los 3 servicios
sin necesidad de parchear internamente.

---

### Slice S-G — Consolidar documentación (post-refactor)

**Depende de:** S-A a S-F cerrados

**Objetivo:** Actualizar documentación para reflejar la nueva arquitectura.

**Archivos a actualizar:**

| Archivo | Qué actualizar | Basado en |
|---|---|---|
| `docs/gen_proc.md` | Diagrama de secuencia — agregar `PhaseEvent` y `PipelineAdapter`. Agregar nota sobre extracción de fases. | Cambios de S-A a S-F |
| `docs/estandar_diseno_architectural.md` | Agregar `src/domain/events.py` al ERD. Agregar `PipelineAdapter` al diagrama de colaboración. Agregar nota sobre estrategia de refactor incremental. | Cambios de S-A a S-F |
| `README.md` | Agregar nota sobre Spec-500 y estrategia de clean code evolutiva. | Resumen del proceso |

---

## 4. Estado de Slices

| Slice | Descripción | Depende de | Estado |
|---|---|---|---|
| S-A | PhaseEvent: abstracción de eventos del pipeline | — | **PENDIENTE** |
| S-B | Extraer fase global → `prepare_story()` | S-A | **PENDIENTE** |
| S-C | Extraer ejecución de un beat → `_execute_single_beat` | S-B | **PENDIENTE** |
| S-D | Consolidar loop de beats en `StoryRunner` | S-B, S-C | **PENDIENTE** |
| S-E | Adapter para reporter (decoupling) | S-A | **PENDIENTE** |
| S-F | Inyección de servicios en DirectorUseCase | S-B, S-C | **PENDIENTE** |
| S-G | Actualizar documentación | S-A → S-F | **PENDIENTE** |

---

## 5. Validación Cross-Spec

| Spec | Relación | Estado |
|---|---|---|
| Spec-312 | Consolidación de `generated_narrative` en CLI/streaming | **RESUELTO** |
| Spec-310 | `CLIContainer` existe; `run_full_from_dto` no implementado (queda para spec posterior) | **PARCIALMENTE RESUELTO** |
| Spec-150 | `Story` god object saneado | **RESUELTO** |
| Spec-180 | Arquitectura del pipeline secuencial — este spec sanea su implementación | VIGENTE |
| Spec-201 | Restricciones SSE (heartbeat, idempotencia, etc.) | **PRESERVAR** en todos los slices |
| Spec-210 | Arquitectura web/streaming | **PRESERVAR** en S-E |

---

## 6. Notas de Diseño

### Sobre los callbacks originales de `execute_full`

Los callbacks (`on_plan_ready`, `on_step_done`, `on_step_start`) están pensados para
el reporter CLI. El spec **no los elimina** — son parte del contrato actual. Lo que
se hace es:
1. Definir `PhaseEvent` como abstracción de dominio.
2. Permitir que `execute_full` yield `PhaseEvent` además del tuple `(beat, journal, elapsed)`.
3. Opcionalmente, un caller puede pasar un listener que traduciría `PhaseEvent` → `ProgressReporter`.

Esto es backward compatible: los callbacks existentes siguen funcionando. El nuevo
canal (yield de `PhaseEvent`) es opt-in.

### Sobre la inyección de servicios

No se refactoriza a constructor full-injection de golpe. El pattern es:
- Parámetros opcionales en constructor.
- Si no se pasan → se crean internamente (comportamiento actual, preserva backward compat).
- Si se pasan → se usan (habilita testing con mocks).
- En slices futuros (post-spec-500), se puede migrar a full-injection cuando el DI container
  soporte la construcción completa.

### Sobre zero breaking changes

Cada slice mantiene la misma API pública. Los únicos archivos que se modifican
son:
- El archivo del smell (refactor interno).
- Tests nuevos (no se modifican tests existentes).
- Documentación (solo en S-G).

---

## 7. Criterios de Cierre del Spec

- [ ] S-A → S-G todos en estado **CERRADO**.
- [ ] `make lint` pasa.
- [ ] `make test` pasa con al menos los mismos tests que antes del refactor.
- [ ] Documentación (`gen_proc.md`, `estandar_diseno_architectural.md`, `README.md`) actualizada.
- [ ] Todo archivo modificado tiene tests de caracterización o tests unitarios nuevos.
- [ ] 0 breaking changes en los call sites: `commands.py`, `stream_router.py`, tests existentes.

---

## 8. Resultados de Implementación (por slice)

*(Se completa cuando se cierra cada slice)*

| Slice | Fecha | Cambio realizado | Archivos tocados | Tests |
|---|---|---|---|---|
| S-A | — | — | — | — |
| S-B | — | — | — | — |
| S-C | — | — | — | — |
| S-D | — | — | — | — |
| S-E | — | — | — | — |
| S-F | — | — | — | — |
| S-G | — | — | — | — |