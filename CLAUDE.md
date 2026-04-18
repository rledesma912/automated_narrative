# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Metodología de trabajo: SDD

Este proyecto usa **Spec-Driven Development**. El flujo obligatorio es:

```
SPECIFY → PLAN → TASKS → IMPLEMENT
```

- Antes de implementar cualquier cambio significativo, verificar si existe un spec en `specs/`.
- Si no existe: crear uno siguiendo `.opencode/skills/spec-driven-development/SKILL.md`.
- No avanzar de fase sin OK explícito del usuario.
- Ejecutar los cambios en slices incrementales siguiendo `.opencode/skills/incremental-implementation/SKILL.md`.
- El idioma de trabajo es **español**.

## Commands

```bash
uv sync                                          # install dependencies
uvicorn src.main:app --reload --host 0.0.0.0 --port 8010  # dev server
python -m src                                    # CLI mode
pytest tests -v --cov=src                        # run all tests
pytest tests/unit/application/ -v               # run a single test directory
ruff check . && ruff format .                    # lint + format
./scripts/bash/init_db.sh                        # initialize SQLite database
```

## Architecture

Clean Architecture with four layers:

```
domain/          → Entities (Story, Beat, NarrativeJournal) + Interfaces (LLMProvider, Repositories)
application/     → Use Cases (CreateStory, Director, Voz) + Services (PromptBuilder, MemoryJournalist)
infrastructure/  → Adapters (Ollama, Gemini, Mock) + SQLite Repositories + MarkdownRenderer
presentation/    → FastAPI routers + Pydantic schemas
core/            → StoryRunner orchestrator (wires everything together)
cli/             → CLI runner, commands, logger
```

The app has two entry points: `src/main.py` (FastAPI) and `src/__main__.py` (CLI via `python -m src`).

## Core Concept: 5-Beat Story Generation

Stories are broken into **5 beats** (narrative units) following the 5-act structure defined in `config/llm_beats_definition.yaml`. That YAML is the single source of truth for beat count and narrative structure. Three LLM roles collaborate per beat:

1. **Director** (`DirectorUseCase`) — plans all 5 beat summaries upfront using `config/prompts_generation/planner.md`. Beat structure (intent, must, must_not) is injected from the YAML.
2. **Voz** (`VozUseCase`) — expands each beat summary into full prose using `config/prompts_generation/voice.md`
3. **MemoryJournalist** — tracks cross-beat coherence (last events, unresolved mysteries, character state) using `config/prompts_generation/journal.md`

The **StoryRunner** (`src/core/orchestrator.py`) orchestrates this flow: plan → for each beat: expand → update journal → persist.

## Data Flow

```
API/CLI → CreateStoryUseCase → DB (story record)
                 ↓
          DirectorUseCase → DB (beat summaries, status=planned)
                 ↓
          For each beat:
            VozUseCase → DB (beat content, status=generated)
            MemoryJournalist → DB (narrative_journal updated)
                 ↓
          MarkdownRenderer → output_stories/
```

## LLM Provider Abstraction

All LLM calls go through the `LLMProvider` protocol (`src/domain/interfaces.py`). Cuatro adapters:
- **OllamaAdapter** — LLM local por defecto. Lee `ollama.host` del YAML.
- **AnthropicAdapter** — API remota. Lee `anthropic.model` del YAML y `ANTHROPIC_API_KEY` del `.env`.
- **GeminiCLIAdapter** — Gemini vía CLI. Lee `gemini.cli_command` y `gemini.model` del YAML.
- **MockLLMAdapter** — respuestas deterministas para tests.

El proveedor activo se define en el YAML (`provider: ollama|anthropic|gemini|mock`). Puede sobreescribirse con la variable de entorno `LLM_PROVIDER` solo para casos de emergencia.

## LLM Configuration (Spec 026 + 027)

**Fuente de verdad: `config/llm_core_definitions.yaml`.** Ese archivo contiene perfiles pre-configurados (provider + roles completos), filtros de respuesta y overrides por modelo. El `.env` se usa **solo** para secretos (`ANTHROPIC_API_KEY`), paths y el override opcional `LLM_PROFILE`.

### Perfiles (Spec 027)

El YAML define múltiples perfiles bajo `profiles:`. Cada perfil es autocontenido: trae su `provider`, bloque adapter-specific (`ollama`/`anthropic`/`gemini`) y los 3 roles (`director`, `voz`, `journal`) con todos sus params. Se activa uno con `active_profile:` en el YAML o con la env `LLM_PROFILE` (override).

Perfiles incluidos: `ollama-natsumura`, `ollama-llama31`, `ollama-mistral`, `anthropic-sonnet`, `gemini-pro`, `gemini-mixto`.

Para agregar un perfil nuevo: copiar un bloque existente bajo `profiles:`, renombrarlo, cambiar modelos/params y activarlo con `active_profile:` o `LLM_PROFILE=<nombre>`.

Precedencia de resolución: `env LLM_PROFILE` → `active_profile:` YAML → fallback `ollama-natsumura`. El resolver está en `src/config.py::_resolve_active_profile`.

**Convención model-por-rol**: el `model` que se envía al LLM vive en `profiles.<perfil>.roles.<rol>.model`. Los bloques adapter (`ollama.host`, `anthropic.model`, `gemini.model`) solo aportan transporte / fallback. Esto permite mezclar modelos dentro del mismo perfil (ej. `gemini-mixto`: Pro para narrativa, Flash para journal).

Campos por rol (`director`, `voz`, `journal`):
- `model`, `temperature`, `num_ctx`, `num_predict`, `stop` (lista de tokens de corte).
- `context_strategy` (solo rol `voz`): `full` | `beat_slice` | `none`. Controla qué parte de la sinopsis se inyecta al LLM por beat para evitar anticipaciones en modelos pequeños.

Filtros (`response_filters`):
- `thinking_tags` — bloques `<think>...</think>` que elimina `ResponseNormalizer`.
- `strip_line_patterns` — regex por línea a descartar (encabezados markdown, separadores, preámbulos).
- `preserve_paragraph_breaks: true` — conserva saltos `\n\n` y colapsa 3+ a 2.
- `model_overrides` — parches extra por substring del nombre del modelo (ej: `natsumura` añade filtros para headers `### Apertura/Desarrollo/Cierre`).

`ResponseNormalizer` (`src/infrastructure/normalizers/response_normalizer.py`) se inyecta en `DirectorUseCase` y `VozUseCase` desde `StoryRunner`. Siempre normaliza el texto raw del LLM antes de persistir.

El archivo `config/llm_response_filters.yaml` está **deprecado** y ya no se lee — su contenido migró a la sección `response_filters` del nuevo YAML.

## Prompt System

Prompts live in `config/prompts_generation/` as Markdown templates:
- `system.md` — base context injected for all roles
- `planner.md` — Director: receives story params + beat specs from YAML, outputs 5 beat summaries
- `voice.md` — Voz: receives beat summary + journal state, outputs prose
- `journal.md` — Journalist: receives beat content, extracts state update

`PromptBuilder` (`src/application/services/prompt_builder.py`) loads and formats these templates.

## Key Environment Variables

El `.env` solo contiene secretos y paths. Toda la config LLM vive en `config/llm_core_definitions.yaml`.

```
ANTHROPIC_API_KEY=...                               # solo si el perfil activo usa AnthropicAdapter
DATABASE_URL=sqlite+aiosqlite:///stories.db
PROMPTS_DIR=./config/prompts_generation
OUTPUT_DIR=./output_stories
BEATS_DEFINITION_FILE=config/llm_beats_definition.yaml
# LLM_PROFILE=ollama-llama31                        # opcional: pisa active_profile del YAML
```

## Specs-Driven Development

The `specs/` directory contains the authoritative specs for all features:
- `specs/001_marco_sdd.md` — SDD framework, naming conventions, architectural rules (read this first for any new feature)
- `specs/002_granular_beat_spec.md` — Backend use cases and domain model details
- `specs/003_ui_granular_spec.md` — Frontend spec
- `specs/004_cli_robust_spec.md` — CLI implementation guide
- `specs/026_llm_core_definitions_spec.md` — unified YAML-driven LLM config, context_strategy, normalizer pipeline
- `specs/027_llm_profiles_spec.md` — pre-configured profiles (active_profile + LLM_PROFILE override)

All new features must follow the naming conventions and layering rules in `001_marco_sdd.md`.

## CLI Commands

```bash
python -m src generate --title "..." --protagonista "..." --sinopsis "..."
python -m src plan <story_id>        # run only Director phase
python -m src narrate <story_id>     # run only Voz phase
python -m src export <story_id>      # export to Markdown
```

## Database

SQLite via `aiosqlite` (async). Three tables:
- `story` — metadata (title, protagonista, relator, escenarios, sinopsis, atmosfera, status)
- `beat` — numbered units per story (summary, content, status, technical_context)
- `narrative_journal` — one row per story tracking cross-beat state (last_events, unresolved_mysteries, physical_emotional_state)

Repositories in `src/infrastructure/database/` implement interfaces defined in `src/domain/interfaces/`.
