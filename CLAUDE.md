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
- Convención de DB: **no se generan scripts de migración**. Si cambia el esquema, actualizar `init_db()` en `src/infrastructure/database/connection.py` y recrear `data/stories.db`.

## Commands

```bash
make install                                     # uv sync + npm install
make api                                         # uvicorn dev server (puerto 8010)
make ui                                          # frontend Express (puerto 3000)
make dev-all                                     # api + ui en paralelo
make db                                          # crea data/stories.db
make test                                        # pytest -v --cov=src
make lint                                        # ruff check + format
uv run python -m src generate --input <yaml>     # generación CLI completa
uv run pytest tests/unit/application/ -v         # subdirectorio de tests
```

## Architecture

Clean Architecture con cuatro capas + cli + core:

```
domain/          → Entities (Story, MacroBeat, NarrativeAnchors, Scenario,
                   NarrativeJournal, GeneratedNarrative, TypedRule)
                   + Interfaces (LLMProvider) + streaming DTOs + exceptions
application/     → Use Cases (CreateStory, Director, Voz, GenerateNarratives,
                   SynopsisBeatMapper, ListBeats, UpdateBeat, GetStory, ListStories)
                   + Services (PromptBuilder Fachada, MemoryJournalist,
                   StoryAnalystService, RuleScenarioResolverService,
                   NarrativeAuditor, StreamingService, StreamSessionManager,
                   ObservabilityService)
infrastructure/  → Adapters (Ollama, Anthropic, GeminiCLI, Mock)
                   + SQLite Repositories + ResponseNormalizer + DebugRenderer
                   + YamlStoryLoader/Exporter + CLIContainer (DI)
presentation/    → FastAPI routers (story, beat, narrative, stream)
                   + Pydantic schemas
core/            → StoryRunner orchestrator (wires everything together)
cli/             → CLI runner, commands, logger, progress reporter, exceptions
```

Dos entry points: `src/main.py` (FastAPI) y `src/__main__.py` (CLI vía `python -m src`).

## Core Concept: 5-Beat Sequential Story Generation (Spec-180)

Las historias se descomponen en **5 macro-beats** siguiendo la estructura de 5 actos definida en `config/llm_beats_definition.yaml`. Ese YAML es la única fuente de verdad para el conteo y la estructura narrativa.

**El VOZ recibe un `narrative_context` completamente pre-construido. Su única responsabilidad es generar prosa literaria.** No interpreta la sinopsis, no infiere contexto, no toma decisiones narrativas.

### Cinco roles LLM por historia

| Rol | Componente | Llamadas | Responsabilidad |
|---|---|---|---|
| **Analyst** | `StoryAnalystService` | 1 (global) | Extrae los 5 `NarrativeAnchors` (pilares) de la sinopsis |
| **Resolver** | `RuleScenarioResolverService` | 1 (global) | Distribuye reglas y escenarios a cada beat (JSON) |
| **Mapper** | `SynopsisBeatMapper.map_one()` | 5 (una por beat) | Extrae qué ocurre en el beat N + identifica el escenario activo |
| **Voz** | `VozUseCase.narrate()` | 5 (una por beat) | Expande `narrative_context` a prosa literaria |
| **Journal** | `MemoryJournalist.extract()` | 5 (una por beat) | Extrae `memory_snapshot` del beat narrado |

**Total: 17 llamadas LLM por historia** (1 analyst + 1 resolver + 5×3).

### Los 5 Pilares de Resonancia Narrativa (Spec-160, estáticos, extraídos una sola vez)

| Campo | Estadio Freytag | Qué captura |
|---|---|---|
| `resonance_hamartia` | Exposición | La grieta psicológica del narrador — vulnerabilidad preexistente |
| `resonance_hybris` | Acción Ascendente | La Transgresión — lógica que permite cruzar la frontera |
| `resonance_anagnorisis` | Clímax | La Violación de lo Sagrado — detalle sensorial insoportable |
| `resonance_peripeteia` | Acción Descendente | La Trampa Espacial — el entorno como antagonista |
| `resonance_residual` | Desenlace | La Mancha Residual — el daño observable que permanece |

Mapeo 1:1: Beat N recibe el Pilar N. No hay `anchor_priorities`. Definición canónica en `config/llm_narrative_definition.yaml`.

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

## Data Flow (Spec-180 + Spec-312)

```
API/CLI → CreateStoryUseCase → DB (story record)
                 ↓
          DirectorUseCase.execute_full():

            [1] StoryAnalystService.extract_anchors()
                → NarrativeAnchors (1 LLM call)
                → DB (narrative_anchors)

            [2] RuleScenarioResolverService.resolve_distribution()
                → rule_distribution: {beat_id: {rules, scenario_index}} (1 LLM call)

            Para cada beat 1..5:
            [3a] mapper.map_one()                → MacroBeat.summary + active_scenario_id (1 LLM call)
                 build_narrative_context()       → MacroBeat.narrative_context (sin LLM)
                 → DB (macro_beat: summary + narrative_context)

            [3b] voz.narrate()                   → MacroBeat.content (1 LLM call)
                 → DB (macro_beat: content + status=completed)

            [3c] journalist.extract()            → MacroBeat.memory_snapshot + NarrativeJournal (1 LLM call)
                 → DB (macro_beat.memory_snapshot, narrative_journal)
                 ↓
          [Spec-312] StoryRunner._consolidate_narrative(story):
              GenerateNarrativesUseCase.consolidate_and_save()
              → DB (generated_narrative: nueva variante UUID, "title · timestamp")
                 ↓
          DebugRenderer (opcional --debug) → output_stories/debug_*.md
```

El mismo flujo aplica al pipeline web vía SSE (`stream_story` en `streaming_service.py`): tras el último beat, consolida la variante y enriquece el evento `done` con `narrative_id` antes de marcar la historia `completed`.

## LLM Provider Abstraction

Todas las llamadas LLM atraviesan el protocolo `LLMProvider` (`src/domain/interfaces.py`). Cuatro adapters en `src/infrastructure/adapters/`:

- **OllamaAdapter** — LLM local por defecto. Lee `ollama.host` del YAML.
- **AnthropicAdapter** (Spec-050) — API remota. Lee `anthropic.model` del YAML y `ANTHROPIC_API_KEY` del `.env`.
- **GeminiCLIAdapter** — Gemini vía CLI. Lee `gemini.cli_command` y `gemini.model` del YAML.
- **MockLLMAdapter** — respuestas deterministas para tests; activable con `--mock` en CLI o `--provider mock`.

El proveedor activo se define en el perfil activo del YAML. Override de emergencia: `LLM_PROVIDER` o `--provider` en CLI.

## LLM Configuration (Spec-060 + Spec-070)

**Fuente de verdad: `config/llm_core_definitions.yaml`.** Ese archivo contiene perfiles pre-configurados (provider + roles completos), filtros de respuesta y overrides por modelo. El `.env` se usa **solo** para secretos (`ANTHROPIC_API_KEY`), paths y el override opcional `LLM_PROFILE`.

### Perfiles (Spec-070)

El YAML define múltiples perfiles bajo `profiles:`. Cada perfil es autocontenido: trae su `provider`, bloque adapter-specific (`ollama`/`anthropic`/`gemini`) y los **4 roles** (`story_analyst`, `director`, `voz`, `journal`) con todos sus params. Se activa uno con `active_profile:` en el YAML o con la env `LLM_PROFILE` (override).

Perfiles incluidos: `ollama-llama31`, `ollama-mistral`, `ollama-qwen25-14b`, `ollama-mistral-nemo`, `ollama-qwen3-8b`, `ollama-hybrid-voz-qwen3`, `ollama-gemma3-12b`, `anthropic-sonnet`, `gemini-cli`.

Para agregar un perfil nuevo: copiar un bloque existente bajo `profiles:`, renombrarlo, cambiar modelos/params y activarlo con `active_profile:` o `LLM_PROFILE=<nombre>`.

Precedencia de resolución: `env LLM_PROFILE` → `active_profile:` YAML. El resolver vive en `src/config.py`.

**Convención model-por-rol**: el `model` que se envía al LLM vive en `profiles.<perfil>.roles.<rol>.model`. Los bloques adapter (`ollama.host`, `anthropic.model`, `gemini.model`) solo aportan transporte / fallback.

Campos por rol (`story_analyst`, `director`, `voz`, `journal`):
- `model`, `temperature`, `num_ctx`, `num_predict`, `stop` (lista de tokens de corte).

> **Nota:** `context_strategy` fue eliminado en Spec-180. Con `narrative_context` pre-ensamblado ya no tiene sentido controlar qué fragmento de sinopsis llega al VOZ.

Filtros (`response_filters`, Spec-080):
- `thinking_tags` — bloques `<think>...</think>` que elimina `ResponseNormalizer`.
- `strip_line_patterns` — regex por línea a descartar (encabezados markdown, separadores, preámbulos).
- `preserve_paragraph_breaks: true` — conserva saltos `\n\n` y colapsa 3+ a 2.
- `model_overrides` — parches extra por substring del nombre del modelo.

`ResponseNormalizer` (`src/infrastructure/normalizers/response_normalizer.py`) se inyecta en `DirectorUseCase` y `VozUseCase` desde `StoryRunner`. Siempre normaliza el texto raw del LLM antes de persistir.

## Prompt System (Spec-170)

Prompts viven en `config/prompts_generation/` como templates Markdown. `PromptBuilder` (`src/application/services/prompt_builder.py`) actúa como **Fachada** que delega en estrategias (`CompactStrategy`, `FrontierStrategy`) y servicios de apoyo (`PersonaService`, `TemplateLoader`). Método clave: `build_narrative_context(macro_beat, beat_anchors, prev_snapshot) → str` — determinístico, sin LLM.

| Archivo | Rol | Descripción |
|---|---|---|
| `story_analyst_system_compact.md` | Analyst system | Curador literario — define los 5 pilares aristotélicos de resonancia |
| `story_analyst_compact.md` | Analyst user | Extrae 5 secciones `## resonance_*` |
| `synopsis_mapper_system_compact.md` | Mapper system | Instrucciones para extracción extractiva |
| `synopsis_mapper_one_compact.md` | Mapper user | Sinopsis + cronologic_scenarios + anclajes + beat spec → ESCENARIO + EVENTOS |
| `voice_system_compact.md` | Voz system | `{relator}`, `{atmosfera}`, `{protagonistas}`, `{reglas}` — estable por historia |
| `journal.md` | Journal | Extrae `{last_events}`, `{unresolved_mysteries}`, `{physical_emotional_state}` |

## Web & Streaming (Spec-210)

- **Frontend:** Express + EJS + HTMX (`frontend/`). Único origen para el browser. Proxy interno `/api/*` → `CORE_API_URL`.
- **Streaming:** `stream_story()` (`src/application/services/streaming_service.py`) traduce `DirectorUseCase.execute_full()` a `StreamEvent` (`status`, `beat_start`, `beat_done`, `heartbeat`, `done`, `stream_error`). Heartbeat cada 15s (no negociable).
- **Idempotencia:** `StreamSessionManager` (singleton) garantiza un único productor por `story_id`. Conexiones extra se atan a la misma sesión y reciben replay buffer.
- **Wizard de autoría (Spec-220):** 5 pasos, persiste YAML canónico round-trip con `python -m src export-yaml` (Spec-302).
- **Galería de relatos (Spec-311 + Spec-312):** lista variantes de `generated_narrative`, switcher por relato, CTA delete con confirmación HTMX.

## Key Environment Variables

El `.env` solo contiene secretos y paths. Toda la config LLM vive en `config/llm_core_definitions.yaml`.

```
ENV=dev
API_HOST=0.0.0.0:8010                              # host:puerto del Core API
PORT=3010                                          # puerto reservado para Playwright
ANTHROPIC_API_KEY=...                              # solo si el perfil activo usa AnthropicAdapter
DATABASE_URL=sqlite+aiosqlite:///data/stories.db
PROMPTS_DIR=./config/prompts_generation
OUTPUT_DIR=./output_stories
BEATS_DEFINITION_FILE=config/llm_beats_definition.yaml
# LLM_PROFILE=ollama-llama31                       # opcional: pisa active_profile del YAML
# OLLAMA_HOST=http://host.docker.internal:11434    # opcional: pisa el host del perfil
```

`frontend/.env` (independiente):
```
PORT=3000
CORE_API_URL=http://localhost:8010
```

## Specs-Driven Development

El directorio `specs/` contiene las specs autoritativas. Lectura obligatoria al abordar una feature:

| Spec | Tema |
|---|---|
| `010_marco_sdd.md` | Framework SDD, naming conventions, reglas arquitecturales |
| `040_progress_reporter_cli.md` | Reporter CLI con spinner y timing |
| `050_anthropic_provider.md` | AnthropicAdapter |
| `060_llm_core_definitions_spec.md` | YAML unificado + normalizer pipeline |
| `070_llm_profiles_spec.md` | Perfiles pre-configurados + override |
| `080_response_normalizer_scope.md` | Alcance del normalizer |
| `120_cli_service_container_spec.md` | `CLIContainer` (DI para la CLI) |
| `130_persistencia_campos_narrativa_spec.md` | Persistencia de campos narrativos |
| `140_dominio_anemico_spec.md` | Lucha contra el dominio anémico |
| `150_story_god_object_spec.md` | Refactor del `Story` god object |
| `160_freytag_resonance_spec.md` | 5 Pilares Aristotélicos |
| `170_prompting_asertivo_spec.md` | Prompts compact para modelos locales |
| `180_saneamiento_architectural_narrativo.md` | Pipeline secuencial + `narrative_context` pre-baked |
| `210_arquitectura_web_y_streaming.md` | Express + SSE + StreamSessionManager |
| `220_motor_de_autoria_wizard_y_yaml.md` | Wizard de 5 pasos + bidireccionalidad YAML |
| `222_journal_relacional_spec.md` | Journal relacional cross-beat |
| `230_ciclo_de_vida_y_gestion_historias.md` | Estados de historia + artefactos |
| `300_refactor_dominio_varios_relatos.md` | `GeneratedNarrative` (variantes) |
| `301_limpieza_markdown_mejoras_ui.md` | Limpieza Markdown + mejoras UI |
| `302_fix_cli_input_yaml_loader.md` | Fix `--input` YAML loader |
| `310_limpieza_arquitectural_post_302.md` | Saneo post-302 (eliminación de renderers/parsers obsoletos) |
| `311_fix_galeria_ver_relato_y_delete.md` | Galería: switcher de variantes + delete |
| `312_fix_persistencia_generated_narrative.md` | Persistencia automática de `generated_narrative` desde CLI/SSE |

Toda feature nueva debe respetar las convenciones de naming y layering definidas en `010_marco_sdd.md`.

## CLI Commands

Argumentos reales del runner (`src/cli/runner.py`):

```bash
uv run python -m src generate --input input_stories/<file>.yaml [--mock] [--debug] [--hasta <checkpoint>]
uv run python -m src generate --title "..." --protagonist "..." --relator primera_persona|tercera_persona \
       --escenarios "Casa/Pueblo" --sinopsis "..." --atmosfera "..."
uv run python -m src generate --story-id <uuid>           # retoma una historia ya creada
uv run python -m src plan     --title "..."               # solo plan
uv run python -m src narrate  --story-id <uuid> --beats 1,2,3
uv run python -m src export   --story-id <uuid> --format md
uv run python -m src export-yaml <story_id>               # round-trip Story → YAML (Spec-302)
```

Checkpoints válidos para `--hasta` (Spec-040): `analyst`, `mapper:1..5`, `voz:1..5`, `journal:1..5`.

## Database

SQLite vía `aiosqlite` (async). `init_db()` en `src/infrastructure/database/connection.py` define el esquema completo. **Ocho tablas** tras Spec-180/300/312:

| Tabla | Spec | Descripción |
|---|---|---|
| `story` | base | Metadata: title, protagonista, relator, sinopsis, atmosfera, narrative_brief, storyteller_config, personajes, status, file_path |
| `rule` | 130 | Reglas tipadas por historia (content, type, intensity) |
| `macro_beat` | 180 | Unidades narrativas; ver detalle abajo. Renombrada desde `beat`. |
| `macro_beat_rule` | 130 | Tabla de unión M:N entre `macro_beat` y `rule` |
| `scenario` | 180 | Escenarios cronológicos del input (story_id FK, order_index, name) |
| `narrative_anchors` | 160 | Los 5 pilares por historia (`resonance_*`) |
| `narrative_journal` | 222 | Estado vivo cross-beat (last_events, unresolved_mysteries, physical_emotional_state) |
| `generated_narrative` | 300/312 | Variantes consolidadas del relato (UUID por corrida, title con timestamp) |

Esquema de `macro_beat`:

| Columna | Descripción |
|---|---|
| `summary` | Evento del beat extraído por el Mapper |
| `active_scenario_id` | FK → `scenario.id`; escenario activo identificado por el Mapper |
| `active_scenario_description` | Descripción denormalizada para debugging |
| `narrative_context` | Contexto pre-ensamblado recibido por el VOZ (persiste para debugging) |
| `content` | Prosa generada por el VOZ |
| `status` | `pending` \| `in_progress` \| `completed` |
| `type` | Tipo Freytag (`exposicion`, `accion_ascendente`, `climax`, `accion_descendente`, `desenlace`) |
| `technical_context` | Notas técnicas opcionales del Director |

Repositorios en `src/infrastructure/database/repositories/`:
- `SQLStoryRepository`
- `SQLBeatRepository`
- `SQLGeneratedNarrativeRepository` (Spec-300, poblada automáticamente desde Spec-312)

## API Endpoints (FastAPI)

Todos prefijados con `/api/v1`:

```
# story_router
POST   /stories
GET    /stories
GET    /stories/{story_id}
PATCH  /stories/{story_id}
PATCH  /stories/{story_id}/status
PATCH  /stories/{story_id}/file-path
DELETE /stories/{story_id}

# beat_router
GET    /stories/{story_id}/beats
PUT    /stories/{story_id}/beats/{beat_number}
POST   /stories/{story_id}/beats/{beat_number}

# narrative_router (Spec-300)
POST   /story-templates/{story_template_id}/generate-narrative
GET    /story-templates/{story_template_id}/narratives
GET    /generated-narratives/{narrative_id}
GET    /generated-narratives/{narrative_id}/text
DELETE /generated-narratives/{narrative_id}

# stream_router (Spec-210)
GET    /stories/{story_id}/stream         # SSE
GET    /stories/{story_id}/full
GET    /health
GET    /config/active-profile
GET    /system/events
```

## Diagrama de Secuencia — Pipeline Completo (Spec-180 + Spec-312)

```
CLI/API     StoryRunner   DirectorUseCase  Analyst  Resolver  Mapper  VozUseCase  MemoryJournalist  GenerateNarrativesUseCase
   │             │              │             │         │        │         │               │                  │
   │  run_full   │              │             │         │        │         │               │                  │
   │────────────>│              │             │         │        │         │               │                  │
   │             │ execute_full │             │         │        │         │               │                  │
   │             │─────────────>│             │         │        │         │               │                  │
   │             │              │ extract_anchors        │         │        │         │               │                  │
   │             │              │────────────>│         │        │         │               │                  │
   │             │              │ NarrativeAnchors [1 LLM]         │        │         │               │                  │
   │             │              │<────────────│         │        │         │               │                  │
   │             │              │             resolve_distribution │        │         │               │                  │
   │             │              │──────────────────────>│        │         │               │                  │
   │             │              │ rule_distribution [1 LLM]       │         │               │                  │
   │             │              │<──────────────────────│        │         │               │                  │
   │             │              │             │         │        │         │               │                  │
   │             │              │ ════ LOOP beat 1..5 ═══════════════════════════════════════════════════════│
   │             │              │             │         │        map_one  │         │               │                  │
   │             │              │──────────────────────────────────>│      │ [1 LLM]│         │                  │
   │             │              │             │         │        │ MacroBeat(summary, active_scenario_id)           │
   │             │              │<─────────────────────────────────│       │         │               │                  │
   │             │              │             │         │        │         │               │                  │
   │             │              │ build_narrative_context [sin LLM]│        │         │               │                  │
   │             │              │             │         │        │         │               │                  │
   │             │              │             │         │        │ narrate(macro_beat) [1 LLM]                       │
   │             │              │──────────────────────────────────────────>│         │               │                  │
   │             │              │ MacroBeat + content                       │         │               │                  │
   │             │              │<──────────────────────────────────────────│         │               │                  │
   │             │              │             │         │        │         │ extract │ [1 LLM]                  │
   │             │              │────────────────────────────────────────────────────>│                  │
   │             │              │ (snapshot, journal)                                  │                  │
   │             │              │<───────────────────────────────────────────────────-│                  │
   │             │              │             │         │        │         │               │                  │
   │             │ yield (beat, journal, elapsed)        │        │         │               │                  │
   │             │<─────────────│             │         │        │         │               │                  │
   │             │  beat_repo.save(...)                  │        │         │               │                  │
   │             │              │ ════ FIN LOOP ═══════════════════════════════════════════════════════════════│
   │             │                                                                  │                  │
   │             │ [Spec-312] _consolidate_narrative(story)                         │                  │
   │             │──────────────────────────────────────────────────────────────────────────────────>│
   │             │ GeneratedNarrative (nueva variante UUID)                                          │
   │             │<─────────────────────────────────────────────────────────────────────────────────│
   │  Story (con beats + narrative_id)                                                              │
   │<────────────│                                                                                   │
```

El mismo patrón aplica al pipeline web vía `stream_story()` (Spec-210), que envuelve a `DirectorUseCase.execute_full()` y emite `StreamEvent` por SSE; al finalizar invoca `consolidate_and_save()` y enriquece el evento `done` con `narrative_id`.
