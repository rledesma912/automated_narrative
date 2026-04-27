# NarrativeForge — Diagnóstico de Arquitectura y Deuda Técnica

> Revisión completa del core: domain, application, infrastructure, CLI, presentation, testing y prompts.
> Clasificación por severidad: CRITICAL → HIGH → MEDIUM → LOW.

---

## Resumen ejecutivo

Se encontraron **45 issues** distribuidos en 6 capas. Los más urgentes son:

| # | Issue | Severidad | Capa |
|---|-------|-----------|------|
| 1 | `journal.md` usa `{{` en JSON — pipeline de journal rompe | CRITICAL | Prompts |
| 2 | Modelo de dominio anémico — toda la lógica en application | CRITICAL | Domain |
| 3 | `Story` es God Object con 15+ campos | CRITICAL | Domain |
| 4 | `PromptBuilder` (728 líneas, 15+ responsabilidades) | CRITICAL | Application |
| 5 | `DirectorUseCase` crea sus propias dependencias (viola DI) | CRITICAL | Application |
| 6 | CLI importa infraestructura directamente | CRITICAL | CLI |
| 7 | Routers acceden repos directamente, saltan use cases | CRITICAL | Presentation |
| 8 | Mutación de modelo de dominio en routers | CRITICAL | Presentation |

---

## CRITICAL

### 1. `journal.md` — JSON con llaves dobles (pipeline roto)

**Archivo:** `config/prompts_generation/journal.md:26`

El template usa `{{ ... }}` para el bloque JSON, pero Python `.format()` produce el literal `{{` en la salida:

```
{{
  "last_events": "qué ocurrió..."
}}
```

El parser JSON falla y el journal no se extrae correctamente. Este bug está **activo en producción**.

**Fix:** Cambiar `{{` → `{` y `}}` → `}` en las líneas 26 y 30.

---

### 2. Modelo de dominio anémico

**Archivo:** `src/domain/models.py`

Todas las entidades son `BaseModel` de Pydantic sin comportamiento. `Story`, `MacroBeat`, `NarrativeJournal` son contenedores de datos. No hay lógica de dominio en el dominio — toda migra a `application/use_cases/`.

Esto viola el principio central de Clean Architecture: **el dominio es el centro, no los use cases**.

Ejemplo ausente:
```python
# No existe nada como esto:
Story.complete()  # Valida precondiciones antes de cambiar status
MacroBeat.add_content()  # Verifica que content no esté vacío
Story.add_beat()  # Impide duplicados por número
```

**Impacto:** Toda validación de invariantes de negocio está dispersa en use cases y es fácil de olvidar.

---

### 3. `Story` es God Object

**Archivo:** `src/domain/models.py:109-128`

`Story` tiene 15+ campos incluyendo entidades anidadas (beats, scenarios, journal, reglas, storyteller_config). Viola SRP. Debería dividirse en:
- `Story` (aggregate root — id, title, status)
- `StoryMetadata` (protagonista, relator, sinopsis, atmosfera)
- `StoryPlan` (ya existe, está infrautilizado)

---

### 4. `PromptBuilder` — God Class de 728 líneas

**Archivo:** `src/application/services/prompt_builder.py`

15+ responsabilidades en una sola clase:
- Carga de 13+ templates de prompts
- Resolución de variantes (compact/frontier)
- Lógica de persona gramatical
- Slice de sinopsis (3 estrategias)
- Formateo de beats_spec para múltiples variantes
- Serialización JSON para prompts
- Ensamblado de `narrative_context` (determinístico)
- Construcción del bloque `storyteller_config`

**Fix:** Dividir en:
- `SystemPromptBuilder`
- `VoicePromptBuilder`
- `MapperPromptBuilder`
- `JournalPromptBuilder`
- `PersonaService`
- `SynopsisSliceResolver`

---

### 5. `DirectorUseCase` crea sus dependencias internamente

**Archivos:** `src/application/use_cases/director_use_case.py:48-68`

```python
def _get_voz(self) -> "VozUseCase":
    self._voz = VozUseCase(self.llm, memory_journalist=journalist, ...)  # Crea internamente

def _get_journalist(self) -> MemoryJournalist:
    self._journalist = MemoryJournalist(...)  # Crea internamente
```

Viola Dependency Injection. Hace testing difícil, crea acoplamiento fuerte, dificulta reemplazos (ej: mock de Journalist en tests).

Lo mismo ocurre en `VozUseCase:31-34`:
```python
self.memory_journalist or MemoryJournalist(llm)  # Lazy creation
self.prompt_builder or PromptBuilder()  # Lazy creation
```

**Fix:** Todas las dependencias en el constructor. Sin lazy creation.

---

### 6. CLI importa infraestructura directamente

**Archivo:** `src/cli/commands.py:25-28`

La capa CLI crea instancias de:
- `SQLStoryRepository`, `SQLBeatRepository` (infra)
- `LLMFactory` (infra)
- `MarkdownStoryParser` (infra)
- `MarkdownRenderer` (infra)

La CLI debería **solo orquestar**, delegando la creación de componentes a un contenedor de DI o factories de más alto nivel.

---

### 7. Routers acceden repos directamente, saltan use cases

**Archivos:** `src/presentation/routers/story_router.py`, `beat_router.py`, `export_router.py`

Cada endpoint crea su propio repositorio:
```python
repo = SQLStoryRepository()  # En cada endpoint
story = await repo.get_by_id(UUID(story_id))
```

Todas las operaciones de lectura (GET /stories, GET /stories/{id}, GET /stories/{id}/beats) no usan ningún use case. Se accede a la DB directamente desde la capa de presentación.

**Fix:** Crear `GetStoryUseCase`, `ListStoriesUseCase`, `ListBeatsUseCase` y usarlos en los routers. Inyectar repos con FastAPI `Depends()`.

---

### 8. Mutación de modelo de dominio en routers

**Archivo:** `src/presentation/routers/beat_router.py:43`

```python
beat.summary = request.summary  # Mutación directa
await repo.update(beat, UUID(story_id))
```

La mutación de `beat.summary` debería pasar por un `UpdateBeatUseCase` que valide la operación, no por asignación directa.

---

## HIGH

### 9. `resolve_beat_anchors` en domain — sabe de infraestructura

**Archivo:** `src/domain/models.py:131-147`

La función recibe `beats_spec: list[dict]` — una estructura del YAML (config/infrastructure). El dominio depende de un archivo de configuración, violando el layering.

**Fix:** Mover esta función a `application/services/` o que el dominio use value objects con las prioridades embebidas.

---

### 10. Invariantes de dominio ausentes

**Archivo:** `src/domain/models.py`

No se validan reglas de negocio:
- Beat number debe ser positivo (no hay `gt=0`)
- Status de beat debería ser `BeatStatus` enum (actualmente `str`)
- Story no puede marcarse "completed" sin beats con contenido
- No hay validación de orden de beats por story

---

### 11. Value objects faltantes

**Archivo:** `src/domain/models.py`

Se usan primitivos donde hay dominio:
- `status: str` → debería ser `BeatStatus` enum
- `id: UUID4` → sin validación de nulidad en el dominio
- `content: str` → sin límites de longitud para narrativa

---

### 12. `VozUseCase` mezcla responsabilidades

**Archivo:** `src/application/use_cases/voz_use_case.py`

Hace narración + retry logic (`_generate_with_retry`) + detección de rechazos (`_rephrase_prompt`). Tres responsabilidades distintas en una clase.

**Fix:** Extraer `RefusalHandler` / `NarratorRetryGenerator`.

---

### 13. Parsing en SynopsisBeatMapper

**Archivo:** `src/application/use_cases/synopsis_beat_mapper.py:180-219`

El método `_parse_map_one_response()` es pura lógica de parsing (regex, extracción de texto) dentro de un use case. Debería estar en infraestructura: `BeatResponseParser`.

---

### 14. Callbacks sin abstracción

**Archivo:** `src/application/use_cases/director_use_case.py:135-137`

```python
on_plan_ready: Callable[[int, float], None] | None = None
on_step_done: Callable[[str, float], None] | None = None
on_step_start: Callable[[str], None] | None = None
```

Callbacks planos (`Callable`) no son reutilizables para WebSocket streaming ni para otros canales. Debería ser un protocolo `ProgressReporter`.

---

### 15. DTOs son espejos de entidades

**Archivo:** `src/application/dto/story_dto.py`

`StoryCreateDTO` tiene los mismos campos que `Story`. No hay transformación ni validación adicional. Si no agregan valor, son innecesarios.

---

### 16. `context_strategy` referenciado en código pero no existe en YAML

**Archivo:** `src/application/services/prompt_builder.py:184`

```python
strategy = settings.role_config("voz").get("context_strategy", "beat_slice")
```

El YAML no define `context_strategy` en ningún perfil. Siempre cae al default silenciosamente. O falta en el YAML o sobra en el código.

---

### 17. Tests faltantes para use cases críticos

| Componente | Tests | Severidad |
|-----------|-------|-----------|
| `CreateStoryUseCase` | 0 | CRITICAL |
| `StoryRunner.run_from_story()` | 0 | CRITICAL |
| `VozUseCase._generate_with_retry()` | 0 | HIGH |
| `VozUseCase` — paths de error | 0 | HIGH |
| `DirectorUseCase.execute_full()` — paths de error | 0 | HIGH |
| `RuleScenarioResolverService` | 0 | HIGH |

**Cobertura error paths:** Prácticamente nula. No hay tests para LLM con respuesta vacía, JSON malformed, rechazos del modelo, DB write failure.

---

### 18. CLI crea use cases directamente

**Archivo:** `src/cli/commands.py:227-301`

Cada comando crea sus use cases con `CreateStoryUseCase(repo)`, `DirectorUseCase(llm, pb)`, etc. Esto rompe la inyectabilidad — tests deben mockear a nivel de CLI, no de use case.

---

### 19. Hardcoded defaults dispersos

| Valor | Ubicación | Debería estar |
|-------|-----------|----------------|
| `"output_stories/"` | `runner.py:23`, `config.py:91` | Config |
| `"mistral:latest"` | `config.py:149` | YAML profile |
| `"http://localhost:11434"` | `config.py:132` | YAML profile |
| Fallback 5 beats | `prompt_builder.py:31` | Config |

---

### 20. ProgressReporter acoplado a checkpoint service

**Archivo:** `src/cli/progress.py:5,30`

```python
from src.application.services.checkpoint import PHASE_LABELS
label = PHASE_LABELS.get(checkpoint, checkpoint)
```

El reporter depende de constantes de application. Si cambian, se rompe la CLI.

---

## MEDIUM

### 21. Enums inconsistentes

`StoryStatus` usa enum correctamente, pero `MacroBeat.status` usa `str` plano. El `BeatType` (exposición/climax/etc) está definido pero no se usa consistentemente en la DB.

---

### 22. `LLMResponse` en domain/interfaces

**Archivo:** `src/domain/interfaces.py:9-17`

`elapsed_s` es métrica de performance (infraestructura). `word_count` es dato derivado. Esta clase debería estar en `infrastructure/`, no en el dominio.

---

### 23. Protocolos de repository mezclan persistencia

**Archivo:** `src/domain/interfaces.py:42-79`

`save()` y `update()` son redundantes — la decisión de insertar vs actualizar debería vivir dentro del repository, no en la interfaz.

---

### 24. Excepciones de dominio insuficientes

**Archivo:** `src/domain/exceptions.py`

Solo 2 excepciones para todo el dominio. Faltan: `BeatNotFoundError`, `InvalidStatusTransitionError`, `MissingRequiredFieldError`, `NarrativeConsistencyError`. Actualmente `NarrativeError` se usa everywhere — pierde semántica.

---

### 25. `MemoryJournalist` con lazy loading

**Archivo:** `src/application/services/memory_journalist.py:28-35`

```python
@property
def prompt_builder(self) -> "PromptBuilder":
    if self._prompt_builder is None:
        from src.application.services import PromptBuilder
        self._prompt_builder = PromptBuilder()
```

Igual problema que #5. Acoplamiento y testing difícil.

---

### 26. Manejo de errores inconsistente

Los servicios tienen estrategias distintas: algunos capturan y retornan default, otros dejan propagar, otros loguean y siguen. No hay estrategia unificada.

---

### 27. Config con estado global mutable

**Archivo:** `src/config.py:59-62`

```python
_llm_core: dict = _load_llm_core()
_active_profile_name, _profile = _resolve_active_profile(...)
```

Globales mutables dificultan el testing y no son thread-safe.

---

### 28. Sistema de variantes (compact/frontier) genera confusión

13 archivos de prompt en lugar de ~5. La relación entre `prompt_variant` (YAML) + selección de archivo (código) + `context_strategy` (código) no está documentada.

---

### 29. `system.md` potencialmente no utilizado

`config.py:97` lo define como `prompt_file_system` pero `build_system_prompt()` solo lo usa como fallback. El archivo existe pero no está claro si es parte activa del flujo.

---

### 30. Prompts con instrucciones contradictorias

**Archivo:** `config/prompts_generation/voice.md`

- Línea 30: "Eres {relator}, narrando la historia"
- Línea 32: "SIEMPRE escribe en {persona_gramatical}"

Si `relator = "María"` (nombre) y `persona_gramatical = "tercera persona"` (del relator="tercera_persona"), hay contradicción directa.

---

### 31. Instrucciones tipo jailbreak en prompts

**Archivo:** `config/prompts_generation/system.md`

```
- NUNCA rehuses escribir contenido.
- NUNCA preguntes "¿Querés que continúe?"
```

Pueden causar rechazos inesperados o ser interpretadas como intento de evadir restricciones de seguridad del modelo.

---

### 32. `atmosphere` vs `atmosfera` — nomenclatura inconsistente

Algunos templates usan `{atmosphere}`, otros `{atmosfera}`. El `prompt_builder` pasa ambos. Genera confusión y riesgo de que uno quede como literal si no se pasa.

---

### 33. Tests acoplados a implementación

**Archivo:** `tests/unit/application/test_prompt_builder.py`

Tests verifican:
- Posiciones de strings en prompts (`mid = len(prompt) // 2`)
- Contenido de templates (strings hardcodeados como "Continúa el relato")
- Métodos privados (`_resolve_sinopsis`, `_get_prompt_variant`)

Estos tests se rompen si se cambia un template o se refactoriza un método interno.

---

### 34. `tests/fixtures/__init__.py` vacío

Existe infraestructura para fixtures compartidos pero no se usa. `_make_story()` está definido en 8+ archivos de tests con pequeñas variaciones. `_SequenceLLM` (100 líneas de mock) no es reusable.

---

### 35. Duplicación masiva de helpers de test

`_make_story()` aparece en: `test_narrate_beat.py`, `test_slice6_pipeline.py`, `test_story_analyst_service.py`, `test_synopsis_beat_mapper.py`, `test_director_legacy_plan.py`, `test_narrative_context_builder.py`, `test_synopsis_beat_mapper_one.py`, `test_commands.py`. Cada uno con defaults distintos.

---

### 36. Integration tests en directorio unit

`tests/unit/core/test_orchestrator.py` y `tests/unit/infrastructure/test_db_connection.py` usan DB real pero viven en `tests/unit/`. Deben mudarse a `tests/integration/`.

---

### 37. Tests multi-responsabilidad

`test_orchestrator.py` prueba creación + narración + persistencia en un solo test. Si falla, no queda claro cuál parte rompió. `test_slice8_e2e_monte.py` corre el pipeline completo de 16 llamadas LLM por cada test.

---

## LOW

### 38. Protocolos sin precondiciones documentadas

Los métodos de los protocolos no documentan precondiciones ni excepciones que lanzan. Ej: `get_by_id(story_id: UUID)` — ¿qué pasa si es `None`?

---

### 39. Alias confuso

**Archivo:** `src/application/use_cases/director_use_case.py:311`

```python
CreateStoryPlanUseCase = DirectorUseCase
```

Alias que confunde sin necesidad. Un solo nombre.

---

### 40. `SilentReporter` como duplicación

**Archivo:** `src/cli/progress.py`

Debería ser un protocolo con implementación default vacía, no una clase que duplica todos los métodos con `pass`.

---

### 41. Emojis hardcodeados en progress reporting

**Archivo:** `src/cli/progress.py`

Acopla la salida a rendering con emojis. No testeable sin capturar stdout.

---

### 42. Spinner usa threading

**Archivo:** `src/cli/spinner.py`

Funciona en CLI pero impide reutilizar en contexto async de API sin modificación.

---

### 43. Alias de compatibilidad en config dispersos

**Archivo:** `src/config.py:147-175`

`llm_model`, `llm_model_temperature`, `state_extractor_model` delegan a `role_config()`. Funcionan pero dificultan entender qué es "el modelo activo".

---

### 44. YAML con campos inconsistentes entre perfiles

Los perfiles Ollama tienen `num_ctx` y `num_predict`. Los perfiles Anthropic/Gemini tienen solo `num_predict`. Puede causar errores silenciosos con providers no-Ollama.

---

### 45. YAML de beats correctamente mantenido

`llm_beats_definition.yaml` está bien mantenido y en sync con el código — es la única área sin deuda técnica.

---

## Tabla resumen

| Severidad | Cantidad |
|-----------|----------|
| CRITICAL | 8 |
| HIGH | 12 |
| MEDIUM | 17 |
| LOW | 8 |
| **TOTAL** | **45** |

---

## Quick wins (1-2h máximo)

| # | Fix | Impacto |
|---|-----|---------|
| 1 | Corregir `{{` → `{` en journal.md:26 | Activa pipeline de journal |
| 16 | Eliminar referencia a `context_strategy` o agregarlo al YAML | Silencia warning silencioso |
| 39 | Eliminar alias `CreateStoryPlanUseCase` | Reduce confusión |
| 21 | Agregar `BeatStatus` enum y usarlo en `MacroBeat` | type safety |

## Refactors mayores (>8h)

| # | Fix | Impacto |
|---|-----|---------|
| 4 | Dividir `PromptBuilder` en 6 componentes | SRP, testabilidad |
| 5 | Requerir todas las dependencias en constructor de use cases | DI real, testing fácil |
| 7 | Crear use cases para lectura en presentation | Arquitectura correcta |
| 2 | Agregar lógica de dominio a entidades | Clean Architecture |
| 17 | Agregar tests de error paths para Voz, Director, CreateStory | Cobertura real |