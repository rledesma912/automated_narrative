# NarrativeForge Agent Configuration

## Project Context

FastAPI + WebSocket API for automated horror narrative generation using Ollama (local LLM).

**Stack:** Python 3.12, FastAPI, aiosqlite, Ollama, Clean Architecture

## Specs Reference (OBLIGATORIO)

> **ANTES de codificar:** Leer los specs correspondientes

| Spec | Scope | Cuando |
|------|-------|--------|
| [`specs/001_marco_sdd.md`](./specs/001_marco_sdd.md) | Marco SDD | Definiciones obligatorias |
| [`specs/002_granular_beat_spec.md`](./specs/002_granular_beat_spec.md) | Backend | Uso Cases, Domain |
| [`specs/004_cli_robust_spec.md`](./specs/004_cli_robust_spec.md) | CLI | desarrollo de CLI |
| [`specs/003_ui_granular_spec.md`](./specs/003_ui_granular_spec.md) | Frontend | Desarrollo UI |

## Definiciones Críticas (SDD)

| Definición | Valor | Ubicación |
|-----------|-------|-----------|
| **Arquitectura** | Clean Architecture | granular_beat_spec.md §Class Diagram |
| **Naming Python** | PascalCase/clases, snake_case/funciones | granular_beat_spec.md §Code Style |
| **Naming JS** | camelCase/vars, kebab-case/archivos | ui_granular_spec.md §JS Code Style |
| **Naming DB** | singular, snake_case | granular_beat_spec.md §Database Naming |
| **Testing** | pytest-asyncio, coverage >80% | granular_beat_spec.md §Testing Strategy |
| **Linting** | ruff (ignora E501, ARG002, B008, B904) | granular_beat_spec.md §Linting Rules |
| **Puerto API** | 8010 | granular_beat_spec.md §Assumptions |
| **Puerto UI** | 3010 | ui_granular_spec.md §Assumptions |
| **API Base** | http://localhost:8010 | ui_granular_spec.md §Assumptions |

## Skills

Reference `.opencode/skills/` for each phase:
- Define → spec-driven-development
- Plan → planning-and-task-breakdown
- Build → incremental-implementation
- Verify → debugging-and-error-recovery
- Review → code-review-and-quality
- Ship → git-workflow-and-versioning

## Dev Commands

```bash
make install    # uv sync
make dev       # uvicorn with hot-reload (uses API_HOST var)
make test      # pytest -v --cov=src
make lint      # ruff check . && ruff format .
make clean     # remove __pycache__, .pytest_cache, .ruff_cache
```

**Single test:** `pytest tests/unit/test_x.py -v`

**Order:** `make lint` → `make test` → review

## CLI Commands (Core Python)

```bash
# Generación completa (Mock - desarrollo)
python -m src generate \
  --title "La Casa Abandonada" \
  --protagonist "María" \
  --relator tercera_persona \
  --escenarios "Casa embrujada" \
  --sinopsis "Una historia de terror" \
  --atmosfera terror \
  --beats 10

# Generación completa (Ollama real)
python -m src generate \
  --title "La Casa Abandonada" \
  --protagonist "María" \
  --escenarios "Casa embrujada" \
  --sinopsis "Una historia" \
  --atmosfera terror \
  --real

# Solo plan (beats)
python -m src plan --title "Historia" --beats 8

# Narrar beats específicos
python -m src narrate --story-id <UUID> --beats 1,2,3

# Exportar historia
python -m src export --story-id <UUID> --format markdown
```

## Architecture (Backend)

```
src/
├── __main__.py           # Entry point: python -m src
├── main.py           # FastAPI entrypoint
├── config.py         # Env config (pydantic-settings)
├── cli/              # CLI (Core Python - sin API)
│   ├── __init__.py
│   ├── commands.py   # generate, plan, narrate, export
│   ├── exceptions.py # CLIError, ValidationError, etc.
│   ├── logger.py    # Logging robusto (logs/)
│   └── runner.py    # CLI runner (argparse)
├── core/             # Orchestrator (flujo completo)
│   └── orchestrator.py
├── domain/          # Entities + Interfaces
│   ├── models.py    # Story, Beat, NarrativeJournal
│   ├── interfaces.py  # Protocols (LLMProvider, Repository)
│   └── exceptions.py   # Domain exceptions
├── application/     # Use Cases
│   ├── use_cases/  # CreateStory, NarrateBeat, etc.
│   └── services/  # PromptBuilder, MemoryJournalist
├── infrastructure/  # Adapters
│   ├── adapters/  # OllamaAdapter, MockLLMAdapter
│   ├── database/  # SQL repositories
│   └── renderers/  # MarkdownRenderer
└── presentation/   # API (REST)
    └── routers/   # REST endpoints
```

## Important Notes

- **Env vars:** Read from `.env` via pydantic-settings in `src/config.py`
- **DB:** SQLite at `stories.db` (aiosqlite async driver)
- **Ollama:** Must be running locally; models configured per-request
- **Linting:** Ruff ignores E501, ARG002, B008, B904
- **CLI Entry:** Use `python -m src <command>` (no API requerida)
- **Logs:** Se generan en `logs/narrative-{YYYYMMDD}.log`
- **Desarrollo:** Por defecto usa MockLLMAdapter (usar `--real` para Ollama)