# Spec 060 — Deuda Técnica CRITICAL: Correcciones Quirúrgicas (Issues 1–8)

## Contexto

`mejoras.md` identifica 8 issues CRITICAL. Este spec los analiza completos y define
qué se implementa aquí, qué se difiere, y con qué orden de riesgo/ROI.

---

## Clasificación de los 8 CRITICAL

| # | Issue | Acción |
|---|-------|--------|
| 1 | `journal.md` usa `{{` — "pipeline roto" | **Falso positivo** — cerrar con test de regresión |
| 2 | Modelo de dominio anémico | **Diferir → spec 061** |
| 3 | `Story` es God Object | **Diferir → spec 062** |
| 4 | `PromptBuilder` 728 líneas | **Diferir → spec 063** |
| 5 | `DirectorUseCase` viola DI | **Implementar — Slice B** |
| 6 | CLI importa infra directamente | **Diferir → spec 064** |
| 7 | Routers acceden repos sin use cases | **Implementar — Slice C** |
| 8 | Mutación de dominio en router | **Implementar — Slice D** |

---

## Issue 1 — Falso positivo: `journal.md {{`

`mejoras.md` afirma que `{{` produce `{{` literal en el output. Es incorrecto.

Python `.format()` convierte:
- `{{` → `{`
- `}}` → `}`

```python
>>> "{{\"key\": \"val\"}}".format()
'{"key": "val"}'
```

El template `journal.md` es correcto. El LLM recibe JSON bien formado con `{` simples.
**No se modifica ningún archivo.**

**Acción**: Test de regresión en `tests/unit/application/test_journal_prompt.py` que
verifique que el prompt de journal NO contiene `{{` en el output (para prevenir que alguien
"corrija" el `{{` pensando que es un typo y rompa el template).

---

## Issues 2, 3, 4 — Arquitectura: Diferidos con justificación

| Issue | Por qué diferir | Spec |
|-------|----------------|------|
| 2 — Dominio anémico | Agregar comportamiento a entidades requiere migrar lógica de múltiples use cases + tests | 061 |
| 3 — Story God Object | Dividir `Story` implica cambios en DB schema, todos los repositorios, DTOs y tests | 062 |
| 4 — PromptBuilder 728 líneas | Split en ~6 clases actualiza todos los call sites: DirectorUseCase, VozUseCase, mappers, routers | 063 |

Estos tres son refactors de diseño con blast radius muy alto. Requieren specs propios
con slices incrementales y criterios de rollback.

---

## Issue 6 — CLI importa infra: Diferido

`src/cli/commands.py` instancia `SQLStoryRepository`, `SQLBeatRepository`, `LLMFactory`,
`MarkdownRenderer` directamente. El fix correcto es un `ServiceContainer` o `ApplicationFactory`
en `src/infrastructure/`. Se difiere a spec 064 para no comprometer el scope actual.

---

## Issue 5 — DI real en use cases (Slice B)

### Problema

Tres puntos de creación lazy/implícita de dependencias:

**`DirectorUseCase`** (`director_use_case.py:48–68`):
```python
def _get_voz(self) -> VozUseCase:
    self._voz = VozUseCase(self.llm, memory_journalist=journalist, ...)  # crea internamente

def _get_journalist(self) -> MemoryJournalist:
    self._journalist = MemoryJournalist(...)  # crea internamente
```

**`VozUseCase`** (`voz_use_case.py:31–32`):
```python
self.memory_journalist = memory_journalist or MemoryJournalist(llm)  # lazy fallback
self.prompt_builder = prompt_builder or PromptBuilder()              # lazy fallback
```

**`MemoryJournalist`** (`memory_journalist.py:28–35`):
```python
@property
def prompt_builder(self) -> PromptBuilder:
    if self._prompt_builder is None:
        self._prompt_builder = PromptBuilder()  # lazy property
```

### Fix

**`MemoryJournalist`**: Eliminar lazy property. `prompt_builder` se construye en `__init__`
si no se pasa (sin lazy). La propiedad se reemplaza por atributo directo.

**`DirectorUseCase`**: Eliminar `_get_voz()` y `_get_journalist()`. En `__init__`, si
no se reciben `voz` y `journalist`, construirlos ahí (eager, no lazy). Los métodos
`_get_voz()` y `_get_journalist()` se eliminan del API público.

**`StoryRunner` (`orchestrator.py`)**: Construir `MemoryJournalist` explícitamente y
pasarlo a `DirectorUseCase`. `DirectorUseCase` recibe todo en el constructor.

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `src/application/services/memory_journalist.py` | Eliminar lazy property `prompt_builder`; atributo directo en `__init__` |
| `src/application/use_cases/director_use_case.py` | Eliminar `_get_voz()` y `_get_journalist()`; construir eager en `__init__` |
| `src/core/orchestrator.py` | Instanciar `MemoryJournalist` antes de `DirectorUseCase`, pasarlo explícitamente |

### Restricción

`VozUseCase` conserva sus parámetros opcionales (`memory_journalist`, `prompt_builder`)
para no romper call sites en routers y tests que lo instancian directamente.
La diferencia: en el pipeline principal (`StoryRunner → DirectorUseCase → VozUseCase`)
siempre se pasan explícitamente.

---

## Issue 7 — Read use cases para presentation (Slice C)

### Problema

Los endpoints GET no usan ningún use case:

```python
# story_router.py — GET /stories
repo = SQLStoryRepository()
stories = await repo.list_all()  # DB access directo desde router

# story_router.py — GET /stories/{id}
repo = SQLStoryRepository()
story = await repo.get_by_id(UUID(story_id))  # idem

# beat_router.py — GET /stories/{id}/beats
repo = SQLBeatRepository()
beats = await repo.get_by_story(UUID(story_id))  # idem
```

### Fix

Tres use cases nuevos en `src/application/use_cases/`:

| Archivo | Clase | Responsabilidad |
|---------|-------|-----------------|
| `list_stories.py` | `ListStoriesUseCase` | Retorna `list[Story]` desde el repo |
| `get_story.py` | `GetStoryByIdUseCase` | Retorna `Story | None` por UUID |
| `list_beats.py` | `ListBeatsUseCase` | Retorna `list[Beat]` para una historia |

Todos reciben el repositorio en el constructor. Los routers los reciben vía
FastAPI `Depends()`.

**Patrón en routers:**
```python
def get_list_stories_use_case():
    return ListStoriesUseCase(SQLStoryRepository())

@router.get("/stories")
async def list_stories(use_case=Depends(get_list_stories_use_case)):
    stories = await use_case.execute()
    return [StoryResponse(...) for s in stories]
```

### Archivos a modificar/crear

| Archivo | Acción |
|---------|--------|
| `src/application/use_cases/list_stories.py` | Crear |
| `src/application/use_cases/get_story.py` | Crear |
| `src/application/use_cases/list_beats.py` | Crear |
| `src/application/use_cases/__init__.py` | Registrar los 3 nuevos |
| `src/presentation/routers/story_router.py` | Refactorizar `list_stories()` y `get_story()` |
| `src/presentation/routers/beat_router.py` | Refactorizar `list_beats()` |

---

## Issue 8 — Mutación de dominio encapsulada (Slice D)

### Problema

```python
# beat_router.py:43
beat.summary = request.summary  # mutación directa del dominio
await repo.update(beat, UUID(story_id))
```

### Fix

`UpdateBeatUseCase` en `src/application/use_cases/update_beat.py`:

```python
class UpdateBeatUseCase:
    def __init__(self, beat_repo: SQLBeatRepository):
        self.repo = beat_repo

    async def execute(self, story_id: UUID, beat_number: int, new_summary: str) -> Beat:
        beat = await self.repo.get_by_number(story_id, beat_number)
        if beat is None:
            raise StoryNotFoundError(str(beat_number))
        beat.summary = new_summary
        await self.repo.update(beat, story_id)
        return beat
```

El router solo llama `use_case.execute(...)`. La mutación `beat.summary = ...` queda
encapsulada en el use case, no en la capa de presentación.

### Archivos a modificar/crear

| Archivo | Acción |
|---------|--------|
| `src/application/use_cases/update_beat.py` | Crear |
| `src/application/use_cases/__init__.py` | Registrar |
| `src/presentation/routers/beat_router.py` | Refactorizar `update_beat()` |

---

## Testing

### Tests nuevos

| Archivo | Qué verifica |
|---------|-------------|
| `tests/unit/application/test_journal_prompt.py` | `build_journal_prompt()` produce `{` no `{{` en el bloque JSON |
| `tests/unit/application/test_list_stories_use_case.py` | `execute()` delega a `repo.list_all()` |
| `tests/unit/application/test_get_story_use_case.py` | `execute()` delega a `repo.get_by_id()`; retorna `None` si no existe |
| `tests/unit/application/test_list_beats_use_case.py` | `execute()` delega a `repo.get_by_story()` |
| `tests/unit/application/test_update_beat_use_case.py` | Mutación encapsulada; `StoryNotFoundError` si beat no existe |

### Tests a actualizar

| Archivo | Por qué |
|---------|---------|
| `tests/unit/application/test_director_legacy_plan.py` | `DirectorUseCase` cambia constructor (sin `_get_voz`) |
| `tests/unit/application/test_slice6_pipeline.py` | Mismo motivo |
| `tests/unit/core/test_orchestrator.py` | `StoryRunner` cambia wiring |
| `tests/unit/application/test_memory_journalist.py` | Eliminar lazy property |

---

## Documentación

| Archivo | Qué actualizar |
|---------|---------------|
| `CLAUDE.md` — tabla de Use Cases | Agregar `ListStoriesUseCase`, `GetStoryByIdUseCase`, `ListBeatsUseCase`, `UpdateBeatUseCase` |
| `CLAUDE.md` — Data Flow diagram | Aclarar que los routers GET usan use cases |
| `specs/035_director_orquestador_punta_a_punta.md` | Añadir nota: DI es eager en `__init__`, no lazy |

---

## Plan de slices

```
Slice A — Test regresión journal.md (no-bug confirmado)
Slice B — DI: MemoryJournalist + DirectorUseCase + StoryRunner
Slice C — Read use cases + refactor routers GET
Slice D — UpdateBeatUseCase + refactor PUT /beats
Slice E — lint + make test completo
```

Cada slice es independiente y deja el sistema en estado verde antes del siguiente.

---

## Specs diferidos

| Spec | Issue | Título tentativo |
|------|-------|-----------------|
| 061 | 2 | Domain behavior: lógica en entidades |
| 062 | 3 | Story decomposition: God Object → aggregate root |
| 063 | 4 | PromptBuilder split: SRP en 6 componentes |
| 064 | 6 | CLI service container: DI en capa de comandos |

---

## Success Criteria

1. `build_journal_prompt()` produce `{` simple en el bloque JSON (test pasa).
2. `MemoryJournalist` no tiene lazy property — `prompt_builder` es atributo directo.
3. `DirectorUseCase.__init__` construye sus deps sin `_get_voz()` / `_get_journalist()`.
4. `StoryRunner` pasa `journalist` y `voz` explícitamente al `DirectorUseCase`.
5. `GET /stories`, `GET /stories/{id}`, `GET /stories/{id}/beats` usan use cases.
6. `PUT /stories/{id}/beats/{num}` usa `UpdateBeatUseCase`.
7. `make test` pasa (308+ tests).
8. `make lint` pasa.
