# Spec 064 — CLIContainer: Centralizar la construcción de dependencias en el CLI

## Problema

`src/cli/commands.py` — cada función `_*_async` instancia infraestructura directamente:

| Función | Objetos instanciados en el cuerpo |
|---------|-----------------------------------|
| `_generate_async` | `LLMFactory`, `SQLStoryRepository`, `SQLBeatRepository`, `PromptBuilder`, `ProgressReporter`, `DebugCollector`/`NullDebugCollector`, `StoryRunner` |
| `_generate_from_db_async` | ídem (copia exacta de wiring) |
| `_plan_async` | `LLMFactory`, `SQLStoryRepository`, `PromptBuilder`, `CreateStoryUseCase`, `DirectorUseCase` |
| `_narrate_async` | `SQLStoryRepository`, `SQLBeatRepository`, `LLMFactory`, `VozUseCase` |
| `_export_async` | `SQLStoryRepository`, `SQLBeatRepository` |

Consecuencias:
1. **Duplicación**: `_generate_async` y `_generate_from_db_async` hacen el mismo wiring de 6 objetos.
2. **Violación de SRP**: las funciones de lógica de CLI también son responsables de ensamblar la infraestructura.
3. **Testabilidad**: imposible probar un comando con repos/LLM falsos sin parchar los módulos.
4. **Fragilidad**: agregar un parámetro nuevo (ej. `debug_collector`) requiere editar N funciones.

## Decisión de diseño

Extraer un `CLIContainer` — clase no-singleton que encapsula la construcción de todos los
componentes necesarios para el CLI. Las funciones `_*_async` lo instancian una vez y preguntan
lo que necesitan.

```
ANTES:  _generate_async → new SQLStoryRepository()
                        → new SQLBeatRepository()
                        → LLMFactory.get_provider(...)
                        → new PromptBuilder()
                        → new ProgressReporter()
                        → DebugCollector() if debug else NullDebugCollector()
                        → StoryRunner(...)

DESPUÉS: _generate_async → CLIContainer(use_mock, provider, debug)
                                 .story_runner(output_dir)
```

## Ubicación

`src/infrastructure/container.py`

Vive en `infrastructure/` porque ensambla adaptadores de infraestructura. No es dominio ni
aplicación; es el punto de entrada del shell al grafo de dependencias.

## Interfaz del contenedor

```python
class CLIContainer:
    def __init__(
        self,
        use_mock: bool = False,
        provider: str | None = None,
        debug: bool = False,
        output_dir: Path | None = None,
    ) -> None: ...

    # Componentes base (lazy, cacheados como propiedades)
    @property
    def llm(self) -> LLMProvider: ...
    @property
    def story_repo(self) -> SQLStoryRepository: ...
    @property
    def beat_repo(self) -> SQLBeatRepository: ...
    @property
    def prompt_builder(self) -> PromptBuilder: ...
    @property
    def reporter(self) -> ProgressReporter: ...
    @property
    def debug_collector(self) -> DebugCollector | NullDebugCollector: ...

    # Use cases
    def create_story_use_case(self) -> CreateStoryUseCase: ...
    def director_use_case(self) -> DirectorUseCase: ...
    def voz_use_case(self) -> VozUseCase: ...

    # Runner (requiere output_dir)
    def story_runner(self, output_dir: Path) -> StoryRunner: ...
```

**Diseño lazy**: cada propiedad se crea la primera vez que se accede y queda cacheada en
`self._<nombre>`. Las funciones de factory de use cases siempre devuelven una instancia nueva
(son stateful entre llamadas).

## Archivos a crear

```
src/infrastructure/container.py
tests/unit/infrastructure/test_cli_container.py
```

## Archivos a modificar

```
src/infrastructure/__init__.py          → exportar CLIContainer
src/cli/commands.py                     → usar CLIContainer en todas las funciones _*_async
```

## Archivos a NO tocar

Todos los callers fuera de `commands.py` (routers, `StoryRunner`, use cases). Zero blast radius.

## Plan de slices

Cada slice deja los tests verdes antes del siguiente.

```
Slice A — CLIContainer + tests unitarios
          Crear container.py y test_cli_container.py.
          Verificar con MockLLMAdapter que el grafo se ensambla correctamente.

Slice B — Refactorizar _generate_async y _generate_from_db_async
          Ambas funciones se reducen a: container = CLIContainer(...); runner = container.story_runner(output_dir)

Slice C — Refactorizar _plan_async, _narrate_async, _export_async
          Usar container.story_repo, container.beat_repo, container.voz_use_case(), etc.

Slice D — Lint + make test completo
```

## Testing

### Tests nuevos: `test_cli_container.py`

| Test | Qué verifica |
|------|-------------|
| `test_llm_con_mock` | `use_mock=True` → `MockLLMAdapter` |
| `test_llm_cached` | `container.llm is container.llm` (misma instancia) |
| `test_story_repo_es_sql` | `isinstance(container.story_repo, SQLStoryRepository)` |
| `test_beat_repo_es_sql` | `isinstance(container.beat_repo, SQLBeatRepository)` |
| `test_debug_collector_debug_true` | `debug=True` → `DebugCollector` |
| `test_debug_collector_debug_false` | `debug=False` → `NullDebugCollector` |
| `test_story_runner_tipo` | `container.story_runner(tmp_path)` → `StoryRunner` |
| `test_director_use_case_tipo` | `container.director_use_case()` → `DirectorUseCase` |
| `test_create_story_use_case_tipo` | `container.create_story_use_case()` → `CreateStoryUseCase` |

### Tests de regresión

Los tests existentes de `commands.py` (si hay) deben seguir pasando. Las funciones
públicas (`generate`, `plan`, `narrate`, `export_`) no cambian su firma.

## Documentación

| Archivo | Qué actualizar |
|---------|---------------|
| `CLAUDE.md` — sección Architecture | Agregar `CLIContainer` a `infrastructure/` |

## Success Criteria

1. `src/cli/commands.py` no contiene ninguna instanciación directa de `SQLStoryRepository`,
   `SQLBeatRepository`, `PromptBuilder`, `ProgressReporter`, `DebugCollector`, `NullDebugCollector`.
2. `CLIContainer` tiene tests con ≥9 casos cubriendo todos sus métodos públicos.
3. `make test` pasa (todos los tests existentes + los nuevos).
4. `make lint` pasa.
5. Ningún caller fuera de `commands.py` fue modificado.
