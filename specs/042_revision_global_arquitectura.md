# Spec 042 — Revisión Global de Arquitectura, Logs, Prompts y UX Terminal

## 1. Objetivo

Revisión transversal del proyecto para corregir problemas de diseño detectados tras la implementación de Spec-038 y Spec-041. Este spec abarca ocho áreas independientes que pueden implementarse en slices paralelos.

---

## 2. Hallazgos por Área

### 2.1 Responsabilidades de Componentes

#### VozUseCase — dualidad de rutas no resuelta

`VozUseCase` expone dos rutas de narración:

| Método | Template de usuario | Ruta de llamada |
|---|---|---|
| `execute(story, beat, ...)` | `build_beat_prompt()` → `voice_compact.md` | `run_from_story()`, `commands._narrate_async()` |
| `narrate(macro_beat, story)` | `build_voz_user_prompt()` → `narrative_context` inline | Pipeline principal `execute_full()` |

`execute()` construye el contexto narrativo en el prompt de usuario. `narrate()` lo recibe pre-ensamblado. **Las dos rutas son incompatibles en términos de input**. La ruta `execute()` es código legacy que aún se llama desde `run_from_story()` y `commands._narrate_async()`, pero estas rutas no construyen `narrative_context`. La dualidad crea una API confusa: dos métodos públicos con contratos distintos para hacer "lo mismo".

**Corrección**: Documentar explícitamente en el docstring de ambos métodos cuál es el contexto de uso válido. Agregar `@deprecated` o nota clara en `execute()` indicando que es la ruta legacy para beats sin `narrative_context`. No eliminar todavía para no romper `run_from_story`.

#### StoryAnalystService — viola DI

```python
# lines 38-40 en story_analyst_service.py
self.llm = llm
self.prompt_builder = prompt_builder
self.normalizer = ResponseNormalizer(role="story_analyst")  # ignora el normalizer inyectado
```

El `normalizer` recibido por parámetro se descarta silenciosamente. Esto rompe la inyección de dependencias y hace que los tests que inyectan un normalizer mock no tengan efecto.

**Corrección**: Usar el normalizer inyectado si se provee, y solo crear uno interno si `normalizer is None`.

```python
self.normalizer = normalizer if normalizer is not None else ResponseNormalizer(role="story_analyst")
```

#### RuleScenarioResolverService — temperatura hardcodeada

```python
# line 37 en rule_scenario_resolver_service.py
temperature = 0.2  # Baja temperatura para JSON preciso
```

Hardcodea la temperatura en lugar de leerla desde `role_cfg`. No tiene un rol propio (`rule_resolver`) — reutiliza la config de `director`. No hay entrada en `llm_core_definitions.yaml` para este servicio.

**Corrección**: Agregar rol `rule_resolver` en el YAML (o usar `director` con temperatura leída de config, no hardcodeada). Leer `temperature` desde `role_cfg.get("temperature", 0.2)`.

#### StoryRunner — usa `print()` directamente

```python
# lines 122-126 en orchestrator.py
print(f"\n[PAUSA] Pipeline detenido en '{stop_after}'...")
print(f"[PAUSA] Story ID: {story.id}")
```

`StoryRunner` bypasea el `reporter` para imprimir mensajes de checkpoint. Toda comunicación con el usuario debe ir por `reporter`.

**Corrección**: Agregar método `reporter.checkpoint_pause(stop_after, story_id, total_llms, debug_path)` en `ProgressReporter` y `SilentReporter`. Reemplazar los `print()` directos.

#### DirectorUseCase — accede a método privado de PromptBuilder

```python
# line 214 en director_use_case.py
beat_info = self.prompt_builder._get_beat_info(beat_id)
```

Accede al método privado `_get_beat_info()`. 

**Corrección**: Hacer `get_beat_info()` público (quitar el underscore) en `PromptBuilder`.

#### PromptBuilder — escape manual de llaves en `build_rule_resolver_prompt()`

```python
# lines 591-598 en prompt_builder.py
template = template.replace("{{", "___OBRACKET___").replace("}}", "___CBRACKET___")
# ... reemplazos individuales con .replace() ...
template = template.replace("___OBRACKET___", "{").replace("___CBRACKET___", "}")
```

Reemplaza variables con `str.replace()` en lugar de `str.format()` porque el template JSON del prompt tiene llaves literales. El workaround con tokens es frágil y difícil de mantener.

**Corrección**: Escapar las llaves literales del template JSON como `{{` y `}}`, y usar `template.format(...)` directamente.

---

### 2.2 Gestión de Excepciones

#### Jerarquía actual

```
BaseException
  └── CLIError (cli/exceptions.py)
        ├── ValidationError
        ├── StoryNotFoundError   ← duplica domain/exceptions.py:StoryNotFoundError
        ├── OllamaConnectionError
        ├── GenerationError
        └── ExportError

Exception
  └── NarrativeError (domain/exceptions.py)
        ├── StoryNotFoundError
        ├── BeatNotFoundError
        ├── PlanGenerationError
        └── InvalidInputError
```

**Problemas identificados**:

1. **`CLIError` hereda de `BaseException`** (no de `Exception`). Esto hace que los bloques `except Exception` no la capturen, lo cual es un bug potencial. Solo `SystemExit`, `KeyboardInterrupt` y `GeneratorExit` deberían heredar de `BaseException`.

2. **`StoryNotFoundError` está duplicada**: existe en `cli/exceptions.py` y en `domain/exceptions.py`. La versión CLI oscurece la de dominio cuando se hace `from src.cli.exceptions import StoryNotFoundError`.

3. **Wrapping pierde el contexto**: en `commands.py` todos los errores se convierten a `GenerationError(str(e))`, perdiendo el traceback y el tipo original.

4. **No existen**: `LLMProviderError`, `PromptTemplateError`, `ParseError` — errores de infraestructura que hoy lanzan `Exception` genérica.

5. **`_parse_anchors` usa fallback silencioso**: si el LLM no entregó las 4 secciones esperadas, se aplica `_fallback_anchors` con un `logger.warning`. No hay forma de saber en el nivel superior que el analyst falló parcialmente.

**Corrección**:

- Cambiar `CLIError(BaseException)` → `CLIError(Exception)`.
- Eliminar `cli/exceptions.py:StoryNotFoundError` y usar la de dominio.
- Agregar en `domain/exceptions.py`: `LLMProviderError`, `PromptTemplateError`, `ParseError`.
- En `commands.py`: preservar `from … import NarrativeError` y hacer `raise GenerationError(str(e)) from e`.

---

### 2.3 Adherencia al llm_beats_definition.yaml

El pipeline principal respeta el YAML correctamente:
- `num_beats` = `len(macro_beats)` → derivado del YAML, no hardcodeado.
- `anchor_priorities` se usa en `resolve_beat_anchors()`.
- `must`/`must_not`/`success_signal`/`state_change` se inyectan en `build_narrative_context()`.

**Problema**: El CLAUDE.md documenta "16 llamadas LLM por historia (1 analyst + 5×3)". Pero el pipeline actual hace **17**: se agregó `RuleScenarioResolverService.resolve_distribution()` en Spec-041 sin actualizar la documentación. El conteo real es:

```
1 (analyst) + 1 (rule_resolver) + 5×3 (mapper+voz+journal) = 17 llamadas
```

**Corrección**: Actualizar CLAUDE.md, README.md y el diagrama de secuencia para reflejar 17 llamadas (o 18 si el modelo actual requiere ajuste). Actualizar la tabla de roles con `rule_resolver`.

---

### 2.4 ResponseNormalizer — diseño

El diseño de `ResponseNormalizer` está correcto: es un servicio puro configurable desde YAML, sin estado compartido, inyectable. Los problemas son de uso:

| Problema | Ubicación | Corrección |
|---|---|---|
| Ignora normalizer inyectado, crea propio | `StoryAnalystService.__init__` | Usar inyectado si no es None (ver 2.1) |
| `if self.normalizer:` sin instanciación por defecto | `RuleScenarioResolverService.resolve_distribution` | Crear `ResponseNormalizer()` si None en `__init__` |
| Normaliza sin pasar el rol | `VozUseCase.execute()`, `DirectorUseCase._analyze_story()` | Pasar `role=` donde aplique |

**Nota**: La clase en sí no necesita cambios estructurales. Solo correcciones en los sitios de instanciación.

---

### 2.5 Prompts — Inventario y Saneamiento

#### Dos variantes de prompts: compact y frontier

El sistema soporta dos variantes de prompts controladas por `prompt_variant` en el perfil YAML:

- **compact** — prompts concisos optimizados para modelos locales (Ollama). Todos los perfiles activos usan esta variante.
- **frontier** — prompts más extensos y estructurados, pensados para modelos de API (Anthropic, Gemini) que toleran contextos largos.

**Ambas variantes son válidas y deben mantenerse.** Los prompts sin sufijo `_compact` son la implementación frontier — no están en desuso, están en standby hasta que se active un perfil con `prompt_variant: frontier`.

#### Mapa de uso por variante

| Archivo | Variante | Llamado desde | Estado |
|---|---|---|---|
| `story_analyst_system_compact.md` | compact | `build_story_analyst_system()` | ✅ EN USO |
| `story_analyst_compact.md` | compact | `build_story_analyst_prompt()` | ✅ EN USO |
| `story_analyst.md` | **frontier** | `build_story_analyst_prompt()` si variant=frontier | ✅ LISTO (standby) |
| `synopsis_mapper_system_compact.md` | compact | `build_synopsis_mapper_system()` | ✅ EN USO |
| `synopsis_mapper_one_compact.md` | compact | `build_synopsis_mapper_one_prompt()` | ✅ EN USO (ruta principal) |
| `synopsis_mapper_compact.md` | compact | `build_synopsis_mapper_prompt()` | ⚠️ Solo ruta legacy `plan` command |
| `synopsis_mapper.md` | **frontier** | `build_synopsis_mapper_prompt()` si variant=frontier | ✅ LISTO (standby) |
| `rule_resolver_compact.md` | compact | `build_rule_resolver_prompt()` | ✅ EN USO |
| `rule_resolver_system_compact.md` | compact | `build_rule_resolver_system()` | ✅ EN USO |
| `voice_system_compact.md` | compact | `build_voice_system_compact()` | ✅ EN USO |
| `voice_compact.md` | compact | `build_beat_prompt()` en `VozUseCase.execute()` | ⚠️ Solo ruta legacy `execute()` |
| `voice.md` | **frontier** | `_voice_template_path()` si variant=frontier | ✅ LISTO (standby) |
| `system.md` | **frontier** | `build_system_prompt()` / `build_voice_prompt()` | ✅ LISTO (standby) |
| `journal.md` | ambas | `build_journal_prompt()` | ✅ EN USO |
| `synopsis_mapper_compact.md.old` | — | — | 🔴 ELIMINAR |

#### Problema: sin prompts frontier para `rule_resolver`

`rule_resolver_compact.md` y `rule_resolver_system_compact.md` solo existen en variante compact. Si se activa un perfil frontier, `build_rule_resolver_prompt()` cargará el compact de todas formas (no hay rama `else`). Esto es una inconsistencia menor — documentar como deuda técnica.

#### Duplicado detectado

`synopsis_mapper_compact.md` y `synopsis_mapper_one_compact.md` son prácticamente idénticos (difieren solo en una oración introductoria). Ambos comparten el mismo formato de respuesta `ESCENARIO: / EVENTOS:`. El mantenimiento duplicado es riesgo de divergencia.

**Corrección**:

1. Eliminar `synopsis_mapper_compact.md.old`.
2. NO mover ni archivar los prompts frontier (`story_analyst.md`, `synopsis_mapper.md`, `voice.md`, `system.md`) — son parte del sistema.
3. Fusionar `synopsis_mapper_compact.md` con `synopsis_mapper_one_compact.md` — usar solo `synopsis_mapper_one_compact.md` para ambos contextos (el legacy `map()` y el principal `map_one()`). Actualizar `build_synopsis_mapper_prompt()` para delegar a `build_synopsis_mapper_one_prompt()` con `macro_beat_id=0` o similar.
4. Agregar comentario en cabecera de cada prompt indicando: variante (`compact`/`frontier`), rol que lo usa, método de `PromptBuilder` que lo carga.

---

### 2.6 Logs — Naming con turno AM/PM cada 12hs

**Estado actual**: Un archivo por día.
```
logs/narrative-20260424.log
logs/narrative-error-20260424.log
```

**Estado objetivo**: Cuatro archivos por día (turno AM si hora < 12, PM si hora >= 12).
```
logs/narrative-20260424-am.log
logs/narrative-error-20260424_am.log
logs/narrative-20260424-pm.log
logs/narrative-error-20260424_pm.log
```

**Cambios en `src/cli/logger.py`**:

```python
def _setup_loggers(self) -> None:
    now = datetime.now()
    today = now.strftime("%Y%m%d")
    turno = "am" if now.hour < 12 else "pm"

    main_log = self.log_dir / f"narrative-{today}-{turno}.log"
    error_log = self.log_dir / f"narrative-error-{today}_{turno}.log"
    # ... resto igual
```

El logger se instancia una sola vez al importar (`logger = NarrativeLogger()`), por lo que el turno se fija en el momento de inicialización. Si una sesión cruza la medianoche del turno (raro en la práctica), seguirá escribiendo en el archivo del turno de inicio — comportamiento aceptable.

---

### 2.7 Debug MD — Nombre de Prompts por Llamada

El archivo de diagnóstico `debug_prompts_responses_*.md` muestra el contenido completo de cada prompt pero no el nombre del archivo template que se usó. Esto dificulta saber qué variante de prompt generó un resultado.

**Cambios requeridos**:

#### `LLMCallRecord` (debug_collector.py)
Agregar dos campos:
```python
system_prompt_file: str | None = None   # ej: "story_analyst_system_compact.md"
user_prompt_file: str | None = None     # ej: "story_analyst_compact.md"
```

#### `DebugCollector.record()` 
Aceptar los dos campos nuevos como kwargs opcionales.

#### Sitios de llamada (todos los componentes que llaman `debug_collector.record()`)
Pasar los nombres de archivo. Cada componente conoce qué template usó:
- `StoryAnalystService`: `system_prompt_file="story_analyst_system_compact.md"`, `user_prompt_file="story_analyst_compact.md"`
- `SynopsisBeatMapper.map_one()`: `system_prompt_file="synopsis_mapper_system_compact.md"`, `user_prompt_file="synopsis_mapper_one_compact.md"`
- `VozUseCase.narrate()`: `system_prompt_file="voice_system_compact.md"`, `user_prompt_file="(narrative_context inline)"`
- `MemoryJournalist.extract()`: `system_prompt_file=None`, `user_prompt_file="journal.md"`
- `RuleScenarioResolverService`: `system_prompt_file="rule_resolver_system_compact.md"`, `user_prompt_file="rule_resolver_compact.md"`

#### `DebugMarkdownRenderer._call_section()` (debug_renderer.py)
Agregar en la sección "Parámetros de Inferencia":
```markdown
| system_prompt_file | story_analyst_system_compact.md |
| user_prompt_file   | story_analyst_compact.md        |
```

---

### 2.8 Spinner en Terminal Durante Llamadas LLM

**Estado actual**: `ProgressReporter` imprime una línea estática por etapa. No hay feedback visual durante la espera de la respuesta LLM (que puede durar 30-120 segundos con modelos locales).

**Solución**: Spinner ASCII en hilo separado que actualiza la misma línea con `\r` mientras el LLM procesa.

**Diseño**:

Nuevo archivo `src/cli/spinner.py`:

```python
import itertools
import sys
import threading
import time


class Spinner:
    """Spinner de terminal en hilo separado. Compatible con Python asyncio."""
    
    CHARS = ["⠋", "⠙", "⠸", "⠴", "⠦", "⠇"]  # braille spinner
    INTERVAL = 0.12  # segundos entre frames

    def __init__(self, message: str = ""):
        self._message = message
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, message: str | None = None) -> None:
        if message:
            self._message = message
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, final_line: str | None = None) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        sys.stdout.write("\r\033[K")  # limpiar línea
        if final_line:
            sys.stdout.write(final_line + "\n")
        sys.stdout.flush()

    def _spin(self) -> None:
        for char in itertools.cycle(self.CHARS):
            if self._stop_event.is_set():
                break
            sys.stdout.write(f"\r{char}  {self._message}")
            sys.stdout.flush()
            time.sleep(self.INTERVAL)
```

**Integración en `ProgressReporter`** (`src/cli/progress.py`):

Agregar `start_spinner(msg)` y `stop_spinner(final_line)` que delegan a un `Spinner` interno.

**Integración en el pipeline**: Los puntos de activación del spinner son las llamadas LLM. Opciones:

- **Opción A (recomendada)**: Activar desde `ProgressReporter.phase_start()` y desactivar desde `ProgressReporter.step_done()`. El Director llama `on_step_done` cuando cada paso termina.
- **Opción B**: Envolver las llamadas LLM en los adaptadores directamente.

La Opción A es menos invasiva y mantiene toda la UX en la capa CLI.

**Nota**: `SilentReporter.start_spinner/stop_spinner` deben ser no-ops.

---

## 3. Áreas NO cubiertas en este Spec (fuera de scope)

- Refactor mayor del `PromptBuilder` (demasiado grande para este slice).
- Migración completa de la ruta legacy `VozUseCase.execute()` → `narrate()`.
- Cambios en el schema de la DB.
- Nuevas funcionalidades narrativas.

---

## 4. Archivos Afectados

| Archivo | Cambio |
|---|---|
| `src/cli/logger.py` | Naming AM/PM en logs |
| `src/cli/progress.py` | Agregar `start_spinner`/`stop_spinner`, `checkpoint_pause` |
| `src/cli/spinner.py` | **Nuevo** — clase `Spinner` |
| `src/cli/exceptions.py` | `CLIError(Exception)`, eliminar `StoryNotFoundError` duplicada |
| `src/domain/exceptions.py` | Agregar `LLMProviderError`, `PromptTemplateError`, `ParseError` |
| `src/application/services/story_analyst_service.py` | Fix DI normalizer |
| `src/application/services/rule_scenario_resolver_service.py` | Temperatura desde config, normalizer por defecto |
| `src/application/services/debug_collector.py` | Campos `system_prompt_file`, `user_prompt_file` |
| `src/application/services/prompt_builder.py` | `_get_beat_info` → `get_beat_info` (público); fix escape llaves rule_resolver |
| `src/application/use_cases/director_use_case.py` | `_get_beat_info` → `get_beat_info` |
| `src/application/use_cases/voz_use_case.py` | Docstring clarificando rutas |
| `src/core/orchestrator.py` | `print()` → `reporter.checkpoint_pause()` |
| `src/infrastructure/renderers/debug_renderer.py` | Mostrar nombres de prompt files |
| `config/prompts_generation/` | Eliminar `.old`; agregar cabeceras de variante/rol |
| `config/llm_core_definitions.yaml` | Agregar rol `rule_resolver` (o documento de temp de director) |
| `README.md` | Actualización completa (ver Sección 5) |
| `CLAUDE.md` | Conteo 17 llamadas LLM, tabla 5 roles |

---

## 5. README — Estructura Objetivo

El README debe documentar:

1. **Qué es NarrativeForge** — descripción en 3 líneas.
2. **Arquitectura de 5 roles LLM** — tabla actualizada con `rule_resolver`.
3. **Pipeline completo con 17 llamadas** — diagrama de secuencia actualizado.
4. **Configuración rápida** — clonar, `uv sync`, editar `.env`, configurar perfil.
5. **Comandos CLI** — `generate`, `plan`, `narrate`, `export`, flags relevantes.
6. **Input format** — estructura del archivo `.md` de entrada.
7. **Perfiles disponibles** — tabla de perfiles YAML.
8. **Checkpoints `--hasta`** — tabla de valores válidos y efecto.
9. **Flag `--debug`** — qué genera y cómo interpretarlo.
10. **Estructura de carpetas** — `config/`, `src/`, `specs/`, `output/`.
11. **Correr tests** — comando y cobertura esperada.

---

## 6. Plan de Implementación (Slices)

Los slices son independientes y pueden ejecutarse en cualquier orden:

| Slice | Descripción | Archivos principales |
|---|---|---|
| **A** | Fix DI normalizer + temperatura rule_resolver | `story_analyst_service.py`, `rule_scenario_resolver_service.py` |
| **B** | Excepciones — CLIError(Exception), eliminar duplicada, nuevos tipos | `cli/exceptions.py`, `domain/exceptions.py` |
| **C** | Logs AM/PM | `cli/logger.py` |
| **D** | Spinner terminal | `cli/spinner.py` (nuevo), `cli/progress.py` |
| **E** | Debug MD — prompt file names | `debug_collector.py`, `debug_renderer.py`, todos los sitios de `record()` |
| **F** | Saneamiento de prompts | `config/prompts_generation/` (eliminar/archivar) |
| **G** | Fix PromptBuilder — método público + escape rule_resolver | `prompt_builder.py`, `director_use_case.py` |
| **H** | StoryRunner — reporter.checkpoint_pause() | `orchestrator.py`, `progress.py` |
| **I** | README completo actualizado | `README.md`, `CLAUDE.md` |

---

## 7. Criterios de Éxito

- [ ] `pytest tests -v --cov=src` pasa sin regresiones.
- [ ] `ruff check .` sin errores.
- [ ] `python -m src generate --input input_stories/test.md --mock` produce logs con naming `narrative-YYYYMMDD-am/pm.log`.
- [ ] `python -m src generate --input input_stories/test.md --debug` produce debug MD con columna `system_prompt_file` y `user_prompt_file` en la tabla de resumen.
- [ ] Durante `generate` sin `--mock`, el spinner es visible en consola mientras el LLM procesa.
- [ ] No existen archivos `.old` en `config/prompts_generation/`.
- [ ] Cada archivo de prompt tiene cabecera indicando variante y rol.
- [ ] `src/cli/exceptions.py:CLIError` hereda de `Exception`.
- [ ] `StoryAnalystService` usa el normalizer inyectado si no es None.
- [ ] Conteo de llamadas LLM en CLAUDE.md y README.md: 17.

---

## 8. Boundaries SDD

**Always Do**:
- Mantener `SilentReporter` sincronizado con `ProgressReporter` (mismos métodos).
- Los nombres de archivos de prompt en `LLMCallRecord` deben ser el nombre de archivo real, no rutas absolutas.
- Mantener los prompts frontier (`story_analyst.md`, `synopsis_mapper.md`, `voice.md`, `system.md`) — son parte del sistema para perfiles con `prompt_variant: frontier`.

**Never Do**:
- Cambiar el schema de la DB en este spec.
- Eliminar la ruta `VozUseCase.execute()` (rompe `run_from_story`).
- Agregar dependencias externas pesadas solo para el spinner (usar stdlib `threading` + `itertools`).

**Ask First**:
- Fusión de `synopsis_mapper_compact.md` con `synopsis_mapper_one_compact.md` (impacta el comando `plan` legacy).
- Cambios en el YAML de perfiles (afecta usuarios con configuraciones personalizadas).
