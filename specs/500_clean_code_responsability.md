# Spec-500: Saneamiento de Responsabilidades — Clean Code en el Core

**Fecha de apertura:** 6 de mayo de 2026
**Estado:** Living / Backlog
**Prioridad:** Variable (por slice)
**Metodología:** SDD, refactor incremental sin cambio de comportamiento

---

## 1. Objetivo

Spec **viva** que acumula smells de responsabilidad detectados en el código del core (`src/core/`, `src/application/`) durante el desarrollo. No es un refactor único: es un registro evolutivo. Cada smell se anota con evidencia, se prioriza, y se resuelve en un slice independiente cuando el contexto lo permite.

### Criterios de inclusión

- Violaciones claras de SRP (clase que orquesta + persiste + traduce + valida).
- God objects (>300 líneas, >5 dependencias inyectadas, >3 responsabilidades distinguibles).
- Acoplamiento excesivo entre capas (use case que conoce detalles de DB, servicio que arma SSE).
- Métodos largos (>50 líneas) que mezclan niveles de abstracción.
- Duplicación lógica entre el pipeline CLI y el pipeline web/SSE.

### Criterios de exclusión

- Smells ya cubiertos por specs vivas con plan propio (ej: Spec-150 trata el `Story` god object — no duplicar aquí).
- Code smells cosméticos sin impacto en mantenibilidad (naming menor, formato).
- Archivos largos por su naturaleza (templates EJS, YAML de prompts) — esos van a Spec-318 §9.

---

## 2. Smells Detectados (Inventario)

### 2.1 `StoryRunner` — Orquestador con responsabilidades difusas

**Ubicación:** `src/core/story_runner.py`

**Síntoma:** wires the world. Construye el grafo de dependencias completo (adapters, repos, services, use cases), expone `run_full()` para CLI, e incluye `_consolidate_narrative()` (Spec-312) que persiste la variante consolidada al final del pipeline.

**Por qué es un smell:**
- Mezcla **composition root** (DI / wiring) con **lógica de aplicación** (consolidación, manejo de errores del pipeline).
- La consolidación (`_consolidate_narrative`) es lógica de use case, no de orquestación; vive aquí porque "es el lugar donde está la story al final".
- Cualquier cambio en el pipeline obliga a abrir este archivo, aunque el cambio sea downstream.

**Evidencia para acción:**
- [ ] Confirmar `wc -l src/core/story_runner.py`
- [ ] Listar dependencias inyectadas en su constructor
- [ ] Identificar métodos privados que deberían vivir en un `PipelineFinalizer` o `NarrativeConsolidator`

**Plan provisorio:**
- Extraer composition root a `src/core/container.py` (similar al `CLIContainer` ya existente en infra, pero para el core completo).
- Mover `_consolidate_narrative` a un nuevo `application/use_cases/finalize_story.py` (`FinalizeStoryUseCase`).
- `StoryRunner` queda como un facade delgado: instancia container, invoca `DirectorUseCase`, invoca `FinalizeStoryUseCase`.

**Relación con otras specs:** complementa Spec-150 (que trata el dominio anémico `Story`, no el orquestador).

---

### 2.2 `DirectorUseCase.execute_full()` — Loop con tres responsabilidades por iteración

**Ubicación:** `src/application/use_cases/director.py`

**Síntoma:** un único método ejecuta el pipeline completo: 2 LLM calls globales (analyst + resolver) + loop de 5 beats donde cada iteración ejecuta 3 LLM calls (mapper + voz + journal) y persiste 3 veces.

**Por qué es un smell:**
- Un fallo en cualquier punto del loop deja estado parcialmente persistido sin política clara de rollback / resume.
- La forma de "yieldear" progreso (para el reporter CLI y para SSE) está enredada con la lógica de pipeline.
- Las dos integraciones (CLI batch + web streaming) consumen la misma `execute_full()` pero por distintos canales — y `streaming_service.py` (§2.3) reimplementa lógica de progreso.

**Evidencia para acción:**
- [ ] Medir LOC del método
- [ ] Contar puntos de `await repo.save(...)` dentro del método
- [ ] Listar las dependencias del use case y agruparlas por fase (analyst-phase, resolver-phase, beat-phase)

**Plan provisorio:**
- Extraer "ejecución de un beat" (`_execute_beat(beat_n, story, anchors, journal_state)`) a método público — facilita testing y resume parcial.
- Extraer "fase global" (analyst + resolver) a método público — `prepare_story()`.
- Definir un `BeatProgressEvent` en domain como DTO único; CLI y SSE lo consumen y traducen, sin que el use case sepa nada de SSE.

**Relación:** este saneamiento es prerequisito de §2.3.

---

### 2.3 `streaming_service.py` — Traduce eventos + maneja sesiones + decora con narrative_id

**Ubicación:** `src/application/services/streaming_service.py`

**Síntoma:** `stream_story()` envuelve `execute_full()`, traduce cada paso a `StreamEvent`, gestiona heartbeat (15s), y al final invoca `consolidate_and_save()` para enriquecer el evento `done` con `narrative_id`. Encima, `StreamSessionManager` (singleton) administra idempotencia, replay buffer y conexiones múltiples.

**Por qué es un smell:**
- Un solo módulo cubre **traducción de eventos** (responsabilidad de mapper) + **idempotencia / replay** (responsabilidad de session manager) + **finalización del pipeline** (responsabilidad de use case).
- La consolidación final está duplicada: existe en `StoryRunner._consolidate_narrative` (CLI) y en `stream_story()` (web). Mismo bug, dos lugares para arreglarlo.
- Spec-201 ya documentó 5 restricciones críticas de SSE — todas válidas, pero acumuladas en un mismo archivo.

**Evidencia para acción:**
- [ ] `wc -l src/application/services/streaming_service.py`
- [ ] Identificar las 3 responsabilidades como bloques (traducción / sesión / finalización)
- [ ] Verificar que `StreamSessionManager` se pueda extraer a `infrastructure/streaming/`

**Plan provisorio:**
- Extraer `StreamSessionManager` a `infrastructure/streaming/session_manager.py` (es infra, no application).
- Crear `application/services/event_translator.py` que mapea fases del pipeline a `StreamEvent` — recibe el `BeatProgressEvent` que se introduzca en §2.2.
- La consolidación (común a CLI y web) se invoca via `FinalizeStoryUseCase` (§2.1) — un solo lugar.
- `stream_story()` queda como una corutina delgada que conecta: `execute_full()` → translator → session manager → SSE response.

**Restricciones a preservar (Spec-201):**
- Heartbeat con Queue, no con timer paralelo.
- Idempotencia 409 en conexión duplicada.
- Normalizer aplica antes de SSE (no en el cliente).
- `stream_error` es evento, no excepción HTTP.
- Health check antes de conectar.

---

## 3. Cómo se usa esta spec

### Al detectar un smell nuevo

1. Agregar una sub-sección `2.N` con: ubicación, síntoma, por qué es smell, evidencia (checklist), plan provisorio, relación con otras specs.
2. **No abrir refactor inmediato** — solo registrar.
3. Cuando se vaya a abordar uno: el slice se trata como un sub-spec con su propio bloque PLAN → TASKS → IMPLEMENT.

### Al cerrar un smell

- Marcar el sub-bloque como **Resuelto en Spec-NNN** (linkear a la spec dedicada que lo cerró).
- No borrar la entrada — sirve de historial de saneamiento.

### Reglas de saneamiento

- **No refactorizar preventivamente.** Tocar un archivo solo cuando una feature legítima lo requiera, o cuando el smell esté priorizado.
- **No mezclar refactor con feature.** Slice de refactor es slice puro: tests verdes antes y después, mismo comportamiento observable.
- **Tests de caracterización primero.** Antes de extraer algo, asegurar que existe cobertura del comportamiento actual.

---

## 4. Validación Cross-Spec

| Spec relacionada | Relación |
|---|---|
| Spec-150 | God object `Story` (dominio); este spec trata orquestación, no entidades |
| Spec-180 | Define el pipeline secuencial; este spec sanea su implementación |
| Spec-201 | 5 restricciones SSE; deben preservarse en cualquier extracción de §2.3 |
| Spec-210 | Arquitectura web/streaming; §2.3 desempaqueta su implementación |
| Spec-312 | Persistencia de `generated_narrative`; §2.1 y §2.3 consolidan duplicación |
| Spec-318 §9 | Saneamiento EJS; análogo a este spec pero del lado frontend |

---

## 5. Estado General

- [ ] §2.1 StoryRunner — pendiente
- [ ] §2.2 DirectorUseCase.execute_full() — pendiente (prerequisito de §2.3)
- [ ] §2.3 streaming_service.py — pendiente
