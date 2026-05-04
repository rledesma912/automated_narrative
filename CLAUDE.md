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
domain/          → Entities (Story, MacroBeat, NarrativeAnchors, Scenario, NarrativeJournal)
                   + Interfaces (LLMProvider, Repositories)
application/     → Use Cases (CreateStory, Director, Voz, ListStories, GetStoryById, ListBeats, UpdateBeat)
                   + Services (PromptBuilder, MemoryJournalist, StoryAnalystService)
infrastructure/  → Adapters (Ollama, Anthropic, Gemini, Mock)
                   + SQLite Repositories + MarkdownRenderer + DebugRenderer
presentation/    → FastAPI routers + Pydantic schemas
core/            → StoryRunner orchestrator (wires everything together)
cli/             → CLI runner, commands, logger
```

The app has two entry points: `src/main.py` (FastAPI) and `src/__main__.py` (CLI via `python -m src`).

## Core Concept: 5-Beat Sequential Story Generation (Spec-038)

Stories are broken into **5 macro-beats** following the 5-act structure defined in `config/llm_beats_definition.yaml`. That YAML is the single source of truth for beat count, narrative structure, and **anchor priorities** per beat.

**El VOZ recibe un `narrative_context` completamente pre-construido. Su única responsabilidad es generar prosa literaria.** No interpreta la sinopsis, no infiere contexto, no toma decisiones narrativas.

### Cinco roles LLM por historia

| Rol | Componente | Llamadas | Responsabilidad |
|---|---|---|---|
| **Analyst** | `StoryAnalystService` | 1 (global) | Extrae los 4 `NarrativeAnchors` de la sinopsis (JSON estructurado) |
| **Resolver** | `RuleScenarioResolverService` | 1 (global) | Distribuye reglas y escenarios a cada beat (JSON) |
| **Mapper** | `SynopsisBeatMapper.map_one()` | 5 (una por beat) | Extrae qué ocurre en el beat N + identifica el escenario activo |
| **Voz** | `VozUseCase.narrate()` | 5 (una por beat) | Expande `narrative_context` a prosa literaria |
| **Journal** | `MemoryJournalist.extract()` | 5 (una por beat) | Extrae `memory_snapshot` del beat narrado |

**Total: 17 llamadas LLM por historia** (1 analyst + 1 resolver + 5×3).

### Los 5 Pilares de Resonancia Narrativa (Spec-081, estáticos, extraídos una sola vez)

| Campo | Estadio Freytag | Qué captura |
|---|---|---|
| `resonance_hamartia` | Exposición | La grieta psicológica del narrador — vulnerabilidad preexistente |
| `resonance_hybris` | Acción Ascendente | La Transgresión — lógica que permite cruzar la frontera |
| `resonance_anagnorisis` | Clímax | La Violación de lo Sagrado — detalle sensorial insoportable |
| `resonance_peripeteia` | Acción Descendente | La Trampa Espacial — el entorno como antagonista |
| `resonance_residual` | Desenlace | La Mancha Residual — el daño observable que permanece |

Mapeo 1:1: Beat N recibe el Pilar N del YAML. No hay `anchor_priorities`. Definición en `config/llm_narrative_definition.yaml`.

### El `narrative_context` (ensamblado determinístico)

```
narrative_context =
    beat_spec         (del YAML: name, intent, must, must_not, arco emocional)
  + resonance         (pilar N: valor + label_voz — mapeo 1:1 Beat N → Pilar N)
  + synopsis_event    (qué ocurre en este beat, extraído por el Mapper)
  + active_scenario   (escenario activo identificado por el Mapper desde cronologic_scenarios)
  + memory_snapshot   (estado del beat anterior, del Journalist)
```

Ensamblado por `PromptBuilder.build_narrative_context()` — sin LLM.

## Data Flow (Spec-038)

```
API/CLI → CreateStoryUseCase → DB (story record)
                 ↓
          DirectorUseCase.execute_full():

            [1] StoryAnalystService.extract_anchors()
                → NarrativeAnchors (1 LLM call)
                → DB (narrative_anchors table)

            [2] RuleScenarioResolverService.resolve_distribution()
                → rule_distribution: {beat_id: {rules, scenario_index}} (1 LLM call)

            Para cada beat 1..5:
            [3a] analyst.resolve_beat_anchors()  → beat_anchors dict (sin LLM)
                 mapper.map_one()                → MacroBeat.summary + active_scenario_id (1 LLM call)
                 build_narrative_context()       → MacroBeat.narrative_context (sin LLM)
                 → DB (macro_beat: summary + narrative_context)

            [3b] voz.narrate()                   → MacroBeat.content (1 LLM call)
                 → DB (macro_beat: content + status=completed)

            [3c] journalist.extract()            → MacroBeat.memory_snapshot + NarrativeJournal (1 LLM call)
                 → DB (macro_beat: memory_snapshot, narrative_journal)

          MarkdownRenderer → output_stories/
          DebugMarkdownRenderer → output_stories/debug_*.md (si --debug activo)
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

El YAML define múltiples perfiles bajo `profiles:`. Cada perfil es autocontenido: trae su `provider`, bloque adapter-specific (`ollama`/`anthropic`/`gemini`) y los **4 roles** (`story_analyst`, `director`, `voz`, `journal`) con todos sus params. Se activa uno con `active_profile:` en el YAML o con la env `LLM_PROFILE` (override).

Perfiles incluidos: `ollama-llama31`, `ollama-mistral`, `ollama-qwen25-14b`, `ollama-mistral-nemo`, `ollama-qwen3-8b`, `ollama-gemma3-12b`, `anthropic-sonnet`, `gemini-cli`.

Para agregar un perfil nuevo: copiar un bloque existente bajo `profiles:`, renombrarlo, cambiar modelos/params y activarlo con `active_profile:` o `LLM_PROFILE=<nombre>`.

Precedencia de resolución: `env LLM_PROFILE` → `active_profile:` YAML → fallback `ollama-natsumura`. El resolver está en `src/config.py::_resolve_active_profile`.

**Convención model-por-rol**: el `model` que se envía al LLM vive en `profiles.<perfil>.roles.<rol>.model`. Los bloques adapter (`ollama.host`, `anthropic.model`, `gemini.model`) solo aportan transporte / fallback.

Campos por rol (`story_analyst`, `director`, `voz`, `journal`):
- `model`, `temperature`, `num_ctx`, `num_predict`, `stop` (lista de tokens de corte).

> **Nota:** `context_strategy` fue eliminado en Spec-038. Con `narrative_context` pre-ensamblado ya no tiene sentido controlar qué fragmento de sinopsis llega al VOZ.

Filtros (`response_filters`):
- `thinking_tags` — bloques `<think>...</think>` que elimina `ResponseNormalizer`.
- `strip_line_patterns` — regex por línea a descartar (encabezados markdown, separadores, preámbulos).
- `preserve_paragraph_breaks: true` — conserva saltos `\n\n` y colapsa 3+ a 2.
- `model_overrides` — parches extra por substring del nombre del modelo.

`ResponseNormalizer` (`src/infrastructure/normalizers/response_normalizer.py`) se inyecta en `DirectorUseCase` y `VozUseCase` desde `StoryRunner`. Siempre normaliza el texto raw del LLM antes de persistir.

## Prompt System (Spec-038)

Prompts viven en `config/prompts_generation/` como templates Markdown:

| Archivo | Rol | Descripción |
|---|---|---|
| `story_analyst_system_compact.md` | Analyst system | Curador literario — define los 5 pilares aristotélicos de resonancia |
| `story_analyst_compact.md` | Analyst user | Extrae 5 secciones `## resonance_*` (hamartia/hybris/anagnorisis/peripeteia/residual) |
| `synopsis_mapper_system_compact.md` | Mapper system | Instrucciones para extracción extractiva |
| `synopsis_mapper_one_compact.md` | Mapper user | Sinopsis + cronologic_scenarios + anclajes + beat spec → ESCENARIO + EVENTOS |
| `voice_system_compact.md` | Voz system | `{relator}`, `{atmosfera}`, `{protagonistas}`, `{reglas}` — estable por historia |
| `journal.md` | Journal | Extrae `{last_events}`, `{unresolved_mysteries}`, `{physical_emotional_state}` |

`PromptBuilder` (`src/application/services/prompt_builder.py`) carga y formatea los templates. Método clave: `build_narrative_context(macro_beat, beat_anchors, prev_snapshot) → str` — determinístico, sin LLM.

## Key Environment Variables

El `.env` solo contiene secretos y paths. Toda la config LLM vive en `config/llm_core_definitions.yaml`.

```
ANTHROPIC_API_KEY=...                               # solo si el perfil activo usa AnthropicAdapter
DATABASE_URL=sqlite+aiosqlite:///stories.db
PROMPTS_DIR=./config/prompts_generation
OUTPUT_DIR=./output_stories
BEATS_DEFINITION_FILE=config/llm_beats_definition.yaml
# LLM_PROFILE=ollama-llama31                        # opcional: pisa active_profile del YAML
# OLLAMA_HOST=http://host.docker.internal:11434     # opcional: pisa el host del perfil (usado por la API en Docker; CLI en host cae al YAML → localhost)
```

## Specs-Driven Development

The `specs/` directory contains the authoritative specs for all features:
- `specs/001_marco_sdd.md` — SDD framework, naming conventions, architectural rules (leer primero ante cualquier feature nueva)
- `specs/026_llm_core_definitions_spec.md` — unified YAML-driven LLM config, normalizer pipeline
- `specs/027_llm_profiles_spec.md` — pre-configured profiles (active_profile + LLM_PROFILE override)
- `specs/030_synopsis_beat_mapper_spec.md` — SynopsisBeatMapper: extracción extractiva de beats
- `specs/031_prompts_relato_compact.md` — sistema de prompts compact para modelos locales
- `specs/038_anclajes_narrativos.md` — **arquitectura activa**: NarrativeAnchors, pipeline secuencial, narrative_context pre-baked (IMPLEMENTADO)

All new features must follow the naming conventions and layering rules in `001_marco_sdd.md`.

## CLI Commands

```bash
python -m src generate --title "..." --protagonista "..." --sinopsis "..."
python -m src plan <story_id>        # run only Director phase
python -m src narrate <story_id>     # run only Voz phase
python -m src export <story_id>      # export to Markdown
```

## Database

SQLite via `aiosqlite` (async). Cinco tablas tras migración Spec-038:

```
story              — metadata (title, protagonista, relator, escenarios, sinopsis, atmosfera, status)
narrative_anchors  — NarrativeAnchors por historia (resonance_hamartia, resonance_hybris, resonance_anagnorisis, resonance_peripeteia, resonance_residual)
scenario           — escenarios cronológicos del input (story_id FK, order_index, name)
macro_beat         — unidades narrativas (summary, content, status, active_scenario_id,
                     narrative_context, memory_snapshot, technical_context)
narrative_journal  — estado vivo cross-beat (last_events, unresolved_mysteries, physical_emotional_state)
```

Esquema de `macro_beat` (tabla renombrada desde `beat` en Spec-038):

| Columna | Descripción |
|---|---|
| `summary` | Evento del beat extraído por el Mapper |
| `active_scenario_id` | FK → `scenario.id`; escenario activo identificado por el Mapper |
| `narrative_context` | Contexto pre-ensamblado recibido por el VOZ (persiste para debugging) |
| `content` | Prosa generada por el VOZ |
| `memory_snapshot` | JSON del Journalist: `{last_events, unresolved_mysteries, physical_emotional_state}` |

Repositories in `src/infrastructure/database/` implement interfaces defined in `src/domain/interfaces/`.

## Diagrama de Secuencia — Pipeline Completo (Spec-038 + Spec-041)

```
CLI/API     DirectorUseCase  StoryAnalystService  RuleScenarioResolver  SynopsisBeatMapper  VozUseCase  MemoryJournalist
   │               │                  │                    │                     │               │               │
   │  execute_full(story)             │                    │                     │               │               │
   │──────────────>│                  │                    │                     │               │               │
   │               │  extract_anchors()                    │                     │               │               │
   │               │─────────────────>│                    │                     │               │               │
   │               │  NarrativeAnchors [1 LLM call]        │                     │               │               │
   │               │<─────────────────│                    │                     │               │               │
   │               │                  │                    │                     │               │               │
   │               │                  resolve_distribution(story)                │               │               │
   │               │──────────────────────────────────────>│   [1 LLM call]      │               │               │
   │               │                  rule_distribution (JSON por beat)          │               │               │
   │               │<──────────────────────────────────────│                     │               │               │
   │               │                  │                    │                     │               │               │
   │               │════ LOOP beat 1..5 ══════════════════════════════════════════════════════════════════════════│
   │               │                  │                    │                     │               │               │
   │               │  resolve_beat_anchors()               │                     │               │               │
   │               │─────────────────>│                    │                     │               │               │
   │               │  {principal, contexto} [sin LLM]      │                     │               │               │
   │               │<─────────────────│                    │                     │               │               │
   │               │                  │            map_one(story, beat_id, anchors, rules, scenario)             │
   │               │───────────────────────────────────────────────────────────>│   [1 LLM call] │               │
   │               │                  │            MacroBeat(summary, active_scenario_id)        │               │
   │               │<──────────────────────────────────────────────────────────│                │               │
   │               │                  │                    │                     │               │               │
   │               │  build_narrative_context() [sin LLM]  │                     │               │               │
   │               │─────────────────────────────────────────────────────────────────────────────│               │
   │               │  macro_beat.narrative_context          │                     │               │               │
   │               │<────────────────────────────────────────────────────────────────────────────│               │
   │               │                  │                    │                     │               │               │
   │               │                  │              narrate(macro_beat, story) [1 LLM call]     │               │
   │               │────────────────────────────────────────────────────────────────────────────>│               │
   │               │                  │              MacroBeat + content                         │               │
   │               │<────────────────────────────────────────────────────────────────────────────│               │
   │               │                  │                    │                     │               │               │
   │               │                  │                    │              extract(story, beat)   │  [1 LLM call] │
   │               │──────────────────────────────────────────────────────────────────────────────────────────> │
   │               │                  │                    │              (snapshot, journal)    │               │
   │               │<─────────────────────────────────────────────────────────────────────────────────────────-│
   │               │                  │                    │                     │               │               │
   │  yield (beat, journal, elapsed)  │                    │                     │               │               │
   │<──────────────│                  │                    │                     │               │               │
   │               │════ FIN LOOP ════════════════════════════════════════════════════════════════════════════════│
```
