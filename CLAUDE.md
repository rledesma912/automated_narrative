# CLAUDE.md

Guía operativa para Claude Code en este repositorio. Las specs en `specs/` son la fuente autoritativa; este archivo es solo el quickstart.

## Metodología: SDD

Flujo obligatorio: **SPECIFY → PLAN → TASKS → IMPLEMENT**.

- Antes de implementar: verificar si existe spec en `specs/`. Si no, crear uno siguiendo `.opencode/skills/spec-driven-development/SKILL.md`.
- No avanzar de fase sin OK explícito del usuario.
- Slices incrementales (`.opencode/skills/incremental-implementation/SKILL.md`).
- Idioma de trabajo: **español**.
- DB: **no se generan scripts de migración**. Cambios de esquema → actualizar `init_db()` en `src/infrastructure/database/connection.py` y recrear `data/dev/stories.db`.

## Commands

```bash
make install     # uv sync + npm install
make api         # uvicorn dev (8020)
make ui          # frontend Express (3010)
make dev         # api + ui en paralelo
make db          # crea data/dev/stories.db
make test        # pytest -v --cov=src
make lint        # ruff check + format
cd frontend && npm test               # Vitest (unit + integración del proxy)
cd frontend && npx playwright test    # E2E: levanta su propio Core (:8021, DB descartable
                                      # sembrada desde data/dev, LLM mock) + UI (:3021).
                                      # Con BASE_URL=... usa un frontend existente.
uv run python -m src generate --input <yaml>  # CLI completa
```

## Architecture

Clean Architecture con cuatro capas + cli + core:

```
domain/          → Entities, Interfaces (LLMProvider), DTOs streaming, exceptions
application/     → Use Cases + Services (PromptBuilder, StoryAnalyst, MemoryJournalist,
                   RuleScenarioResolver, StreamingService, JobManager, EventBus)
infrastructure/  → Adapters (Ollama/Anthropic/Gemini/Mock) + SQLite repos +
                   ResponseNormalizer + YamlStoryLoader/Exporter + CLIContainer (DI)
presentation/    → FastAPI routers (story, beat, narrative, stream, job, events) + Pydantic
                   schemas + runtime.py (singletons JobManager/EventBus)
core/            → StoryRunner orchestrator
cli/             → CLI runner, commands, logger, progress reporter
```

Entry points: `src/main.py` (FastAPI) y `src/__main__.py` (CLI vía `python -m src`).

## Core Concept: 5-Beat Sequential Story Generation (Spec-180)

Las historias se descomponen en **5 macro-beats** (estructura de 5 actos en `config/llm_beats_definition.yaml` — única fuente de verdad).

**El VOZ recibe un `narrative_context` pre-construido. Su única responsabilidad es generar prosa.** No interpreta sinopsis ni infiere contexto.

### Cinco roles LLM por historia (17 llamadas: 1+1+5×3)

| Rol | Componente | Llamadas | Responsabilidad |
|---|---|---|---|
| Analyst | `StoryAnalystService` | 1 | Extrae 5 `NarrativeAnchors` (pilares Freytag) de la sinopsis |
| Resolver | `RuleScenarioResolverService` | 1 | Distribuye reglas y escenarios a cada beat |
| Mapper | `SynopsisBeatMapper.map_one()` | 5 | Extrae evento del beat N + escenario activo |
| Voz | `VozUseCase.narrate()` | 5 | Expande `narrative_context` a prosa |
| Journal | `MemoryJournalist.extract()` | 5 | Extrae `memory_snapshot` del beat narrado |

**5 Pilares de Resonancia (Spec-160):** mapeo 1:1 Beat N → Pilar N. Hamartia → Hybris → Anagnorisis → Peripeteia → Residual. Definición canónica en `config/llm_narrative_definition.yaml`.

### El `narrative_context` (ensamblado determinístico, sin LLM)

```
narrative_context = beat_spec + resonance + synopsis_event + active_scenario + memory_snapshot
```

Construido por `PromptBuilder.build_narrative_context()`.

## Data Flow (Spec-180 + Spec-312)

```
API/CLI → CreateStoryUseCase → DB
       ↓
  DirectorUseCase.execute_full():
    [1] StoryAnalystService.extract_anchors()           → narrative_anchors (1 LLM)
    [2] RuleScenarioResolverService.resolve_distribution() → rule_distribution (1 LLM)
    Para cada beat 1..5:
      [3a] mapper.map_one()              → MacroBeat.summary + active_scenario_id (1 LLM)
           build_narrative_context()     → MacroBeat.narrative_context (sin LLM)
      [3b] voz.narrate()                 → MacroBeat.content (1 LLM)
      [3c] journalist.extract()          → memory_snapshot + narrative_journal (1 LLM)
       ↓
  StoryRunner._consolidate_narrative() → GenerateNarrativesUseCase.consolidate_and_save()
                                       → generated_narrative (variante UUID)
```

En la web el mismo flujo corre como **job** (Spec-460): `POST /stories/{id}/jobs` → `JobManager` lanza una `asyncio.Task` independiente de la conexión que consume `stream_story()` (`streaming_service.py`). `stream_story` traduce el pipeline a eventos (`status` con `stage`/`beat`/`total_beats`, `beat_start`, `beat_done`, `heartbeat`, `done`, `stream_error`), tras el último beat consolida y enriquece `done` con `narrative_id`. Heartbeat cada 15s.

## LLM Provider Abstraction

Protocolo `LLMProvider` (`src/domain/interfaces.py`). Cuatro adapters en `src/infrastructure/adapters/`: `OllamaAdapter`, `AnthropicAdapter`, `GeminiCLIAdapter`, `MockLLMAdapter` (tests, `--mock`).

Provider activo: definido en perfil del YAML. Override: `LLM_PROVIDER` env o `--provider` CLI.

## LLM Configuration

**Fuente de verdad: `config/llm_core_definitions.yaml`.** Contiene perfiles (provider + roles), filtros de respuesta y overrides por modelo. El `.env` solo guarda secretos y override `LLM_PROFILE`.

- Perfiles autocontenidos bajo `profiles:` (cada uno trae provider, bloque adapter, y los 4 roles `story_analyst`/`director`/`voz`/`journal`).
- Activación: `active_profile:` en YAML o `LLM_PROFILE=<nombre>` (env tiene precedencia). Resolver en `src/config.py`.
- Convención model-por-rol: el `model` que se envía al LLM vive en `profiles.<perfil>.roles.<rol>.model`.
- Filtros (`response_filters`, Spec-080): `thinking_tags`, `strip_line_patterns`, `preserve_paragraph_breaks`, `model_overrides` por substring de modelo. Aplicados por `ResponseNormalizer` antes de persistir.

Detalle completo: Spec-060, Spec-070.

## Prompt System (Spec-170)

Templates Markdown en `config/prompts_generation/`. `PromptBuilder` actúa como Fachada que delega en estrategias (`CompactStrategy`, `FrontierStrategy`) y servicios (`PersonaService`, `TemplateLoader`).

Templates: `story_analyst_*compact.md`, `synopsis_mapper_*compact.md`, `voice_system_compact.md`, `journal.md`.

## Web & Streaming (Spec-210)

- **Frontend:** Express + EJS + HTMX en `frontend/`. Único origen para el browser. Proxy interno `/api/*` → `CORE_API_URL`.
- **Jobs (Spec-460):** generar y regenerar un acto son jobs (`generation_job`). `JobManager` (singleton en `src/presentation/runtime.py`) corre cada job como `asyncio.Task`: cerrar la pestaña no lo detiene, `POST /jobs/{id}/cancel` sí. Un solo job activo por historia (lock + índice único parcial) → 409 con el job existente. Al arrancar, los jobs que quedaron activos pasan a `failed` ("interrumpida por reinicio").
- **Eventos (Spec-460):** `EventBus` en memoria con canales `job:<id>` (detalle, lo usa la sala) y `global` (ciclo de vida `job_*`, lo usa todo el resto). Ids por canal → reconexión con `Last-Event-ID`. Ningún GET arranca trabajo.
- **Cliente:** `public/js/event-bus.js` abre 1 `EventSource` global por pestaña (en `<head>`, sobrevive a hx-boost; se cierra en la sala) y re-emite `forge:*` en el DOM. Consumidores: banda de generación, pie (estado del Core), botones `[data-generation-trigger]` (`generation-guard.js`), galería en vivo y paneles atados a un job. Heartbeat 15s no negociable.
- **Wizard de autoría (Spec-220):** 5 pasos; termina en "Guardar historia" (solo guarda); la generación se lanza desde la galería o la ficha. Round-trip YAML con `python -m src export-yaml` (Spec-302).
- **Galería (Spec-311 + Spec-312):** lista variantes de `generated_narrative` por relato + delete con confirmación HTMX.

## Environment Variables

```
ENV=dev
API_HOST=0.0.0.0:8020
ANTHROPIC_API_KEY=...                              # solo si perfil usa Anthropic
DATABASE_URL=sqlite+aiosqlite:///data/dev/stories.db
PROMPTS_DIR=./config/prompts_generation
BEATS_DEFINITION_FILE=config/llm_beats_definition.yaml
# LLM_PROFILE=ollama-llama31                       # opcional: pisa active_profile
```

`frontend/.env` independiente (dev): `PORT=3010`, `CORE_API_URL=http://localhost:8020`.

## Database

SQLite vía `aiosqlite`. `init_db()` en `src/infrastructure/database/connection.py` define el esquema. **Nueve tablas** (Spec-190 + Spec-460):

- `story`: id, title, protagonista, relator, sinopsis, genero, subgenero, tono, narrator_config (JSON), status, created_at
- `character`: id, story_id, name, role, traits (JSON), order_index
- `rule`: id, story_id, content, type, intensity, applies_to_beat
- `macro_beat`: id, story_id, number, summary, synopsis_beat, generated_act, status, active_scenario_id, active_scenario_description, system_prompt, user_prompt, type
- `scenario`: id, story_id, order_index, name, description
- `narrative_anchors`: id, story_id, resonance_hamartia, resonance_hybris, resonance_anagnorisis, resonance_peripeteia, resonance_residual
- `narrative_journal`: id, story_id, beat_number, last_events, unresolved_mysteries, physical_emotional_state
- `generated_narrative`: id, story_template_id, title, content, status
- `generation_job`: id, story_id, kind (`full_generation`|`regenerate_voz`), status, stage, beat, total_beats, params (JSON), error, narrative_id, created_at, started_at, finished_at — índice único parcial: 1 job activo por historia

Repos en `src/infrastructure/database/repositories/`: `SQLStoryRepository`, `SQLBeatRepository`, `SQLGeneratedNarrativeRepository`, `SQLJobRepository`.

## CLI Commands

```bash
uv run python -m src generate --input <yaml> [--mock] [--debug] [--hasta <checkpoint>]
uv run python -m src generate --story-id <uuid>           # retoma historia
uv run python -m src narrate --story-id <uuid> --beats 1,2,3
uv run python -m src export-yaml <story_id>               # round-trip Story → YAML
```

Checkpoints `--hasta` (Spec-040): `analyst`, `mapper:1..5`, `voz:1..5`, `journal:1..5`.

## API Endpoints (FastAPI, prefijo `/api/v1`)

- `story_router` — CRUD `/stories`, PATCH `status` y `file-path`.
- `beat_router` — `GET/PUT /stories/{id}/beats[/{n}]`.
- `job_router` (Spec-460) — `POST /stories/{id}/jobs` (`full_generation` | `regenerate_voz` {beat, narrative_id}; 202/409), `GET /stories/{id}/jobs/active`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `GET /jobs/{id}/events` (SSE de detalle).
- `events_router` (Spec-460) — `GET /events` (SSE global: `snapshot` + `job_*` + heartbeat).
- `narrative_router` (Spec-300) — `/story-templates/{id}/narratives`, `/generated-narratives/{id}` (GET/DELETE/text).
- `stream_router` (Spec-210) — `GET /stories/{id}/stream` (SSE de **solo lectura**: se ata al job activo o reproduce los beats), `/full`, `/health`, `/config/active-profile`.

## Specs

Las specs autoritativas están en `specs/`. Lectura obligatoria al abordar una feature: el SessionStart hook lista los archivos disponibles. Nombres clave: `010_marco_sdd.md` (convenciones), `180_saneamiento_architectural_narrativo.md` (pipeline), `210_arquitectura_web_y_streaming.md` (SSE), `460_jobs_asincronos_y_bus_sse.md` (jobs + bus de eventos), `500_clean_code_responsability.md` (smells acumulados del core).
