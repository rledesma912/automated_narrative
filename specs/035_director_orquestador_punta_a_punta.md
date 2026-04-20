# Spec 035 — DirectorUseCase como Orquestador Punta a Punta

**Estado:** IMPLEMENTED  
**Fecha:** 2026-04-19  
**Rama destino:** `fix_flow_ollama_local`  
**Motivación:** `StoryRunner` mezcla lógica de dominio LLM con infraestructura (repos, reporter, debug). `DirectorUseCase` es un wrapper delgado que solo delega al mapper. El resultado es responsabilidades difusas: StoryRunner sabe demasiado de LLM, y el Director no dirige nada en realidad. Además, `planner.md`, `planner_compact.md` y `build_planner_prompt()` son dead code desde que `SynopsisBeatMapper` reemplazó el approach creativo del planner.

---

## 1. Objetivo

Tres cambios coordinados:

1. **`DirectorUseCase` = orquestador LLM punta a punta**: plan → narrar → journal, beat-by-beat. Posee toda la lógica de generación.
2. **`StoryRunner` = thin shell de infraestructura**: crear story en DB, consumir el generator del Director, persistir, reportar progreso.
3. **Eliminar dead code**: `planner.md`, `planner_compact.md`, `build_planner_prompt()`, `_planner_template_path()` y sus tests.

---

## 2. Diseño

### 2.1 Nuevo contrato de `DirectorUseCase`

```python
class DirectorUseCase:

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        normalizer: ResponseNormalizer | None = None,
        debug_collector: DebugCollector | None = None,
        voz: VozUseCase | None = None,         # inyectable para tests
        journalist: MemoryJournalist | None = None,  # inyectable para tests
    ): ...

    async def execute(self, story: Story) -> StoryPlan:
        """Planificación solamente. Usado por CLI `plan`. Sin cambios."""

    async def execute_full(
        self,
        story: Story,
        initial_journal: NarrativeJournal | None = None,
        on_plan_ready: Callable[[int, float], None] | None = None,
    ) -> AsyncIterator[tuple[Beat, NarrativeJournal, float]]:
        """Orquestación punta a punta.
        
        Fase 1: SynopsisBeatMapper.map(story) → beats con summaries
                Llama on_plan_ready(num_beats, elapsed) si se provee
        Fase 2: execute_narration(story, beats, initial_journal) → yield cada beat
        """

    async def execute_narration(
        self,
        story: Story,
        beats_to_narrate: list[Beat],
        initial_journal: NarrativeJournal | None = None,
    ) -> AsyncIterator[tuple[Beat, NarrativeJournal, float]]:
        """Narra beats pre-existentes (caso run_from_story).
        
        Yield (beat_completado, journal_actualizado, llm_elapsed) por cada beat.
        """
```

`execute_full()` delega en `execute_narration()` internamente.

Si `voz` y `journalist` no se inyectan, el Director los crea con las dependencias disponibles:
```python
self._voz = voz or VozUseCase(llm, prompt_builder=prompt_builder, normalizer=normalizer, debug_collector=debug_collector)
self._journalist = journalist or MemoryJournalist(llm, prompt_builder=prompt_builder, debug_collector=debug_collector)
```

### 2.2 `StoryRunner` simplificado

`_run_plan()` y `_run_narrate_all()` desaparecen.

```python
async def run_full(self, title, protagonista, ...) -> Story:
    story = await CreateStoryUseCase(self.story_repo).execute(dto)

    director = DirectorUseCase(
        self.llm, self.prompt_builder,
        normalizer=self.normalizer,
        debug_collector=self.debug_collector,
    )

    completed = []
    i, total = 0, self.prompt_builder.num_beats
    t0 = perf_counter()

    async for beat, journal, llm_elapsed in director.execute_full(
        story,
        on_plan_ready=lambda n, t: self.reporter.plan_done(n, t),
    ):
        await self.beat_repo.save(beat, story.id)
        await self.story_repo.save_journal(story.id, journal)
        step_elapsed = perf_counter() - t0
        self.reporter.beat_done(i + 1, total, step_elapsed, llm_elapsed)
        completed.append(beat)
        i += 1
        t0 = perf_counter()

    story.beats = completed
    return story

async def run_from_story(self, story: Story) -> Story:
    pending_beats = [b for b in await self.beat_repo.get_by_story(story.id)
                     if b.status != "completed"]
    journal = await self.story_repo.get_journal(story.id)

    director = DirectorUseCase(self.llm, self.prompt_builder, ...)

    completed = []
    async for beat, journal, llm_elapsed in director.execute_narration(
        story, pending_beats, initial_journal=journal
    ):
        await self.beat_repo.save(beat, story.id)
        await self.story_repo.save_journal(story.id, journal)
        completed.append(beat)

    story.beats = completed
    return story
```

### 2.3 `execute_narration()` — lógica interna

```python
async def execute_narration(self, story, beats_to_narrate, initial_journal=None):
    journal = initial_journal
    completed = []
    for beat in beats_to_narrate:
        beat, journal, elapsed = await self._voz.execute(
            story=story,
            beat=beat,
            previous_beats=completed,
            journal=journal,
        )
        completed.append(beat)
        yield beat, journal, elapsed
```

`VozUseCase.execute()` ya llama a `MemoryJournalist` internamente, por lo que el journal se actualiza en cada vuelta sin que Director lo maneje explícitamente.

---

## 3. Dead code a eliminar

### Archivos de prompts
- `config/prompts_generation/planner.md` — nunca se usa en producción
- `config/prompts_generation/planner_compact.md` — ídem

### Métodos de `PromptBuilder`
- `build_planner_prompt(story: Story) -> str`
- `_planner_template_path() -> str`

`_format_beats_spec()` NO se elimina — lo usa `build_synopsis_mapper_prompt()`.

### Tests
**`tests/unit/application/test_create_story_plan.py`:**
- Eliminar: `test_planner_prompt_sin_formato_abstracto`
- Mantener y adaptar: `test_execute_returns_story_plan`, `test_director_uses_injected_normalizer`
- Tests de parsing de formatos múltiples → mover a `test_beat_parser.py` o mantener si cubren vía Director
- Agregar: tests de `execute_full()` y `execute_narration()` con mocks

**`tests/unit/application/test_prompt_builder.py`:**
- Eliminar: `test_build_planner_prompt`, `test_compact_variant_loads_compact_planner_template`, `test_frontier_variant_loads_standard_planner_template`

---

## 4. Archivos críticos

| Archivo | Cambio |
|---|---|
| `src/application/use_cases/director_use_case.py` | Agregar `execute_full()`, `execute_narration()`, inyección de Voz y Journal |
| `src/core/orchestrator.py` | Eliminar `_run_plan()` y `_run_narrate_all()`; simplificar `run_full()` y `run_from_story()` |
| `src/application/services/prompt_builder.py` | Eliminar `build_planner_prompt()` y `_planner_template_path()` |
| `config/prompts_generation/planner.md` | Eliminar |
| `config/prompts_generation/planner_compact.md` | Eliminar |
| `tests/unit/application/test_create_story_plan.py` | Refactorizar |
| `tests/unit/application/test_prompt_builder.py` | Eliminar 3 tests de planner |

---

## 5. Success Criteria

| Criterio | Verificación |
|---|---|
| `DirectorUseCase.execute_full()` genera los 5 beats completos | `--debug` → debug file con 5 beats con content |
| `StoryRunner.run_full()` no instancia VozUseCase ni MemoryJournalist | grep en orchestrator.py |
| `build_planner_prompt()` eliminado | `grep -r build_planner_prompt src/` → sin resultados |
| `planner.md` y `planner_compact.md` eliminados | `ls config/prompts_generation/` |
| Tests pasan | `pytest tests/unit/ -v` → sin failures |

---

## 6. Boundaries

### Always Do
- `execute_full()` llama `on_plan_ready` ANTES de empezar la narración.
- `execute_narration()` es un async generator — `yield` dentro de un `for` loop sobre los beats.
- Si `voz` no se inyecta, `DirectorUseCase` lo crea con todas las dependencias disponibles en `__init__`.

### Never Do
- `DirectorUseCase` no toca repos ni llama a `beat_repo` / `story_repo`.
- `DirectorUseCase` no escribe archivos a disco.
- `StoryRunner` no instancia `VozUseCase` ni `MemoryJournalist` directamente.
