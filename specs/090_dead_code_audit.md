# Spec 045 — Dead Code Audit: Eliminación de Código Muerto

## Estado

IMPLEMENTADO

---

## Contexto

A lo largo de los specs 038–044 el sistema evolucionó: use cases fueron reemplazados,
repositorios absorbidos por sus pares, DTOs de la capa de aplicación quedaron obsoletos
al migrar los schemas a la capa de presentación, y métodos de interfaces ya no se usaban
en el pipeline real. Este spec consolida la eliminación de ese código acumulado.

---

## Código eliminado

### Archivos completos (5 src + 2 tests)

| Archivo | Razón |
|---|---|
| `src/application/use_cases/export_story.py` | `ExportStoryUseCase` nunca instanciado; export lo hace el router/CLI con `MarkdownRenderer` directamente |
| `src/application/use_cases/voz_batch_use_case.py` | `VozBatchUseCase` + alias `NarrateBatchUseCase` nunca instanciados; pipeline usa `VozUseCase.narrate()` vía `DirectorUseCase` |
| `src/application/dto/beat_dto.py` | `BeatCreateDTO` y `BeatResponseDTO` nunca usados; routers usan `presentation/schemas/response.py` |
| `src/infrastructure/database/repositories/scenario_repository.py` | `SQLScenarioRepository` nunca instanciado; escenarios gestionados en `SQLStoryRepository` |
| `src/infrastructure/database/repositories/narrative_anchors_repository.py` | `SQLNarrativeAnchorsRepository` nunca instanciado; anchors persistidos directamente desde `StoryAnalystService` |
| `tests/unit/infrastructure/test_scenario_repository.py` | Testeaba clase muerta |
| `tests/unit/infrastructure/test_narrative_anchors_repository.py` | Testeaba clase muerta |

### Clases eliminadas de archivos existentes

- `StoryResponseDTO` de `src/application/dto/story_dto.py`
- 6 excepciones de `src/domain/exceptions.py`: `BeatNotFoundError`, `PlanGenerationError`,
  `InvalidInputError`, `LLMProviderError`, `PromptTemplateError`, `ParseError`

### Métodos eliminados

| Archivo | Método | Razón |
|---|---|---|
| `src/domain/interfaces.py` | `BeatRepository.save_batch()` | Protocol nunca llamado en el pipeline |
| `src/domain/interfaces.py` | `StoryRepository.delete()` | Protocol nunca llamado en el pipeline |
| `src/infrastructure/database/repositories/beat_repository.py` | `save_batch()` | Implementación del Protocol muerto |
| `src/infrastructure/database/repositories/story_repository.py` | `delete()` | Implementación del Protocol muerto |
| `src/application/services/memory_journalist.py` | `summarize_beats()` | Nunca llamado; pipeline usa `extract()` |

### Parámetros y campos eliminados

- `module: str = ""` y `line: int = 0` de los 5 métodos de `NarrativeLogger` en `src/cli/logger.py`
  y todos sus call sites en `orchestrator.py`, `commands.py`, `runner.py`, `rule_scenario_resolver_service.py`
- `prompt_file_planner: str = "planner.md"` de `src/config.py`
- `protagonist`, `atmosphere`, `synopsis`, `journal` (campos English alias) de `src/domain/models.py`

### `__init__.py` limpiados

`src/application/use_cases/__init__.py`, `src/application/dto/__init__.py`,
`src/application/__init__.py`, `src/domain/__init__.py`,
`src/infrastructure/database/repositories/__init__.py`

### Documentación

- Eliminada referencia a `./scripts/bash/migrate_038.sh` de `CLAUDE.md` (script no existía)

---

## Tests actualizados

Eliminados tests de métodos/clases muertos; actualizados tests que usaban la API antigua
del logger o los campos English de Story.

## Resultado

- **Antes**: 314 tests pasando
- **Después**: 302 tests pasando (12 tests eliminados por testear código muerto)
- `ruff check --select F401,F811`: 0 errores
