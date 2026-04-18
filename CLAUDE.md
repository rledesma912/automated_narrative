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

All LLM calls go through `src/domain/interfaces/llm_provider.py`. Three adapters exist:
- **OllamaAdapter** — default local LLM (`OLLAMA_HOST`, `LLM_MODEL` env vars)
- **GeminiAdapter** — Google Gemini fallback
- **MockLLMAdapter** — deterministic responses for tests

Switch providers via `LLM_PROVIDER` env var or by injecting adapters in `StoryRunner`.

## Prompt System

Prompts live in `config/prompts_generation/` as Markdown templates:
- `system.md` — base context injected for all roles
- `planner.md` — Director: receives story params + beat specs from YAML, outputs 5 beat summaries
- `voice.md` — Voz: receives beat summary + journal state, outputs prose
- `journal.md` — Journalist: receives beat content, extracts state update

`PromptBuilder` (`src/application/services/prompt_builder.py`) loads and formats these templates.

## Key Environment Variables

```
OLLAMA_HOST=http://127.0.0.1:11434
LLM_MODEL=Tohur/natsumura-storytelling-rp-llama-3.1:8b
DATABASE_URL=sqlite+aiosqlite:///stories.db
PROMPTS_DIR=./config/prompts_generation
OUTPUT_DIR=./output_stories
BEATS_DEFINITION_FILE=config/llm_beats_definition.yaml
DIRECTOR_TEMPERATURE=0.4
VOZ_TEMPERATURE=0.6
STATE_EXTRACTOR_TEMPERATURE=0.3
```

## Specs-Driven Development

The `specs/` directory contains the authoritative specs for all features:
- `specs/001_marco_sdd.md` — SDD framework, naming conventions, architectural rules (read this first for any new feature)
- `specs/002_granular_beat_spec.md` — Backend use cases and domain model details
- `specs/003_ui_granular_spec.md` — Frontend spec
- `specs/004_cli_robust_spec.md` — CLI implementation guide

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
