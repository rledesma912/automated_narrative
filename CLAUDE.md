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
                   ScenarioResolver, StreamingService, JobManager, EventBus)
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

### Cuatro roles LLM por historia (16 llamadas: 1+5×3)

| Rol | Componente | Llamadas | Responsabilidad |
|---|---|---|---|
| Analyst | `StoryAnalystService` | 1 | Extrae 5 `NarrativeAnchors` (pilares Freytag) de la sinopsis |
| Resolver | `ScenarioResolverService` | 0 | Distribuye escenarios a cada beat — determinístico desde Spec-410 (las reglas activas las deriva `Story.active_rules_for_beat()`) |
| Mapper | `SynopsisBeatMapper.map_one()` | 5 | Extrae evento del beat N + escenario activo |
| Voz | `VozUseCase.narrate()` | 5 | Expande `narrative_context` a prosa |
| Journal | `MemoryJournalist.extract()` | 5 | Extrae `memory_snapshot` del beat narrado |

**5 Pilares de Resonancia (Spec-160):** mapeo 1:1 Beat N → Pilar N. Hamartia → Hybris → Anagnorisis → Peripeteia → Residual. Definición canónica en `config/llm_narrative_definition.yaml`.

### El `narrative_context` (ensamblado determinístico, sin LLM)

```
narrative_context = beat_spec + resonance + synopsis_event + active_scenario + entity_exposure + memory_snapshot
```

Construido por `PromptBuilder.build_narrative_context()` → `NarrativeContextAssembler`. `entity_exposure` solo existe si la historia tiene entidades (Spec-450).

### Entidades — la amenaza (Spec-450)

- Opcionales, hasta 3 por historia (`Story.entities`); la primera es la **principal**. Cada una: nombre, naturaleza (catálogo filtrado por género), descripción, manifestaciones, límites y `reveal_level` (`nunca` | `insinuada` | `progresiva` | `explicita`).
- `config/llm_beats_definition.yaml`: `reveal_rules` por beat (las reglas de revelación de `must`/`must_not` dependen del nivel de la **principal**; `default` = sin entidades) y `entity_exposure` por beat → vocabulario `entity_exposures` (`show` = campos de la ficha que ve la Voz, `guide` = instrucción). `BeatSpecRepository.get_by_id(beat, reveal_level)` / `exposure_for()`.
- Analyst y Mapper reciben las fichas completas; la Voz, solo los campos que la exposición del acto permite (con «señales» no ve ni nombre ni naturaleza). El Journal devuelve `entity_state` (tabla `entity_journal`) y viaja a la memoria del acto siguiente y a la regeneración de un acto.
- **Regresión cero:** sin entidades los prompts son idénticos (placeholders `{amenaza_section}` / `{entity_state_field}` pegados a líneas existentes). Snapshots: `tests/fixtures/snapshots/beat_reveal.json` y `pipeline_prompts.json` (`SNAPSHOT_UPDATE=1` para regenerarlos a propósito).
- Presupuesto de tokens: `scripts/measure_entity_prompts.py` (pipeline real + tokenizer del modelo vía Ollama).

## Data Flow (Spec-180 + Spec-312)

```
API/CLI → CreateStoryUseCase → DB
       ↓
  DirectorUseCase.execute_full():
    [1] StoryAnalystService.extract_anchors()           → narrative_anchors (1 LLM)
    [2] ScenarioResolverService.resolve_distribution()  → rule_distribution (sin LLM)
    Para cada beat 1..5:
      [3a] mapper.map_one()              → MacroBeat.summary + active_scenario_id (1 LLM)
           build_narrative_context()     → MacroBeat.narrative_context (sin LLM)
      [3b] voz.narrate()                 → MacroBeat.content (1 LLM)
      [3c] journalist.extract()          → memory_snapshot + narrative_journal (+ entity_journal) (1 LLM)
       ↓
  StoryRunner._consolidate_narrative() → GenerateNarrativesUseCase.consolidate_and_save()
                                       → generated_narrative (variante UUID)
```

En la web el mismo flujo corre como **job** (Spec-460): `POST /stories/{id}/jobs` → `JobManager` lanza una `asyncio.Task` independiente de la conexión que consume `stream_story()` (`streaming_service.py`). `stream_story` traduce el pipeline a eventos (`status` con `stage`/`beat`/`total_beats`, `beat_start`, `beat_done`, `heartbeat`, `done`, `stream_error`), tras el último beat consolida y enriquece `done` con `narrative_id`. Heartbeat cada 15s.

## LLM Provider Abstraction

Protocolo `LLMProvider` (`src/domain/interfaces.py`). Adapters en `src/infrastructure/adapters/`: `OllamaAdapter`, `AnthropicAdapter`, `GeminiCLIAdapter`, `MockLLMAdapter` (tests, `--mock`) y `RoleRoutingAdapter`.

Provider activo: definido en perfil del YAML. Override: `LLM_PROVIDER` env o `--provider` CLI.

**Proveedor por rol (Spec-480):** un rol puede declarar `provider` en el perfil (`roles.voz.provider: anthropic`); si no, usa el del perfil. Con un solo proveedor `LLMFactory` devuelve el adapter de siempre; si los roles mezclan proveedores, un `RoleRoutingAdapter` despacha cada llamada al adapter de su rol (todas pasan `role`). `/health` verifica cada proveedor en uso y `/config/active-profile` muestra el de cada rol.

**`AnthropicAdapter`:** sin `temperature` para los modelos que no la aceptan (Sonnet 5, Opus 5, Opus 4.7/4.8, Fable); `thinking` por rol (`adaptive` / `disabled` — en Sonnet 5 / Opus 5 omitirlo **piensa**); `effort` en `output_config`; `max_tokens` = `num_predict` con piso 16000 si piensa; texto de los bloques `text`; `refusal` → `LLMRefusalError`, `max_tokens` → error; `LLMResponse.input_tokens/output_tokens`. Tests con `tests/support/fake_anthropic.py` (tipos reales del SDK, sin llamadas).

## LLM Configuration

**Fuente de verdad: `config/llm_core_definitions.yaml`.** Contiene perfiles (provider + roles), filtros de respuesta y overrides por modelo. El `.env` solo guarda secretos y override `LLM_PROFILE`.

- Perfiles autocontenidos bajo `profiles:` (cada uno trae provider, bloque adapter, y los 4 roles `story_analyst`/`director`/`voz`/`journal`).
- Activación: `active_profile:` en YAML o `LLM_PROFILE=<nombre>` (env tiene precedencia). Resolver en `src/config.py`.
- Convención model-por-rol: el `model` que se envía al LLM vive en `profiles.<perfil>.roles.<rol>.model`.
- Perfil híbrido `ollama-gemma3-12b-voz-sonnet5` (Spec-480): la Voz en `claude-sonnet-5`, el resto en `gemma3:12b`. **No activo**; cuesta ~US$ 0,08 por relato (~US$ 0,13 con `thinking: adaptive`). Evaluarlo con `scripts/evaluate_voice.py --profile ollama-gemma3-12b-voz-sonnet5 --yes` (sin `--yes` solo muestra el costo estimado y no genera).
- Filtros (`response_filters`, Spec-080): `thinking_tags`, `strip_line_patterns`, `preserve_paragraph_breaks`, `model_overrides` por substring de modelo. Aplicados por `ResponseNormalizer` antes de persistir.

Detalle completo: Spec-060, Spec-070.

## Prompt System (Spec-170)

Templates Markdown en `config/prompts_generation/`. `PromptBuilder` actúa como Fachada que delega en estrategias (`CompactStrategy`, `FrontierStrategy`) y servicios (`PersonaService`, `TemplateLoader`).

Templates: `story_analyst_*compact.md`, `synopsis_mapper_*compact.md`, `voice_system_compact.md`, `journal.md`.

**Voz (Spec-470):** `voice_system_compact.md` (compact) y `system.md` (frontier) comparten la guía de oficio `voice_craft.md` (ritmo según la intensidad del acto, sugerir antes que nombrar el miedo, cierre en una imagen, primera persona, léxico) vía `{guia_oficio}`, y el bloque «CÓMO LLAMÁS A CADA PERSONAJE» (`{parentescos}`: el rol de cada personaje leído desde quien narra). La lista de clichés prohibidos vive en `voice_cliches.txt` (una por línea; la usan el prompt y las métricas). `PromptBuilder._voice_extras()` completa los tres builders que usan esos templates; `narrator_name()` resuelve quién narra (`storyteller_name` o `storyteller_id`). El encabezado del evento del `narrative_context` dice en qué persona y como quién contarlo.

**Evaluar la prosa:** `uv run python scripts/evaluate_voice.py --label <nombre> --runs 2 --out <dir> [--variants sin,con] [--voz-temperature 0.5] [--mock]` genera «El monte prohibido» con el perfil activo en una DB temporal y mide clichés, parentescos candidatos (se revisan a mano), nombre del narrador fuera de diálogo y 4-gramas repetidos (`scripts/voice_metrics.py`). ~4 min por relato con `gemma3:12b`.

## Web & Streaming (Spec-210)

- **Frontend:** Express + EJS + HTMX en `frontend/`. Único origen para el browser. Proxy interno `/api/*` → `CORE_API_URL`.
- **Jobs (Spec-460):** generar y regenerar un acto son jobs (`generation_job`). `JobManager` (singleton en `src/presentation/runtime.py`) corre cada job como `asyncio.Task`: cerrar la pestaña no lo detiene, `POST /jobs/{id}/cancel` sí. Un solo job activo por historia (lock + índice único parcial) → 409 con el job existente. Al arrancar, los jobs que quedaron activos pasan a `failed` ("interrumpida por reinicio").
- **Eventos (Spec-460):** `EventBus` en memoria con canales `job:<id>` (detalle, lo usa la sala) y `global` (ciclo de vida `job_*`, lo usa todo el resto). Ids por canal → reconexión con `Last-Event-ID`. Ningún GET arranca trabajo.
- **Cliente:** `public/js/event-bus.js` abre 1 `EventSource` global por pestaña (en `<head>`, sobrevive a hx-boost; se cierra en la sala) y re-emite `forge:*` en el DOM. Consumidores: banda de generación, pie (estado del Core), botones `[data-generation-trigger]` (`generation-guard.js`), galería en vivo y paneles atados a un job. Heartbeat 15s no negociable.
- **Wizard de autoría (Spec-220 + Spec-440):** 5 pasos definidos en `frontend/config/ui_definitions.yaml`; termina en "Guardar historia" (solo guarda); la generación se lanza desde la galería o la ficha. Round-trip YAML con `python -m src export-yaml` / `import-yaml` (Spec-302, Spec-440).
  - Opciones dinámicas por `source:` — `genre_catalog` (Género → Subgénero desde `GET /catalog/genres`, `depends_on`; value = ID), `characters` (el narrador lista solo personajes con nombre; `submitStep` lo valida → 422 con el paso re-renderizado) y `entity_natures` (Spec-450: naturalezas del género de la sesión).
  - Grupo «La Amenaza» en el paso 4 (Spec-450): `wizard_card_list` con `startEmpty` (sin cards hasta «Agregar entidad», máx. 3) y `firstSuffix` («— PRINCIPAL»); `maxlength` = topes del dominio. Una naturaleza que no corresponde al género se descarta; una card con datos sin naturaleza no se puede guardar.
  - Las páginas 422 del wizard se muestran pese a `hx-boost` (`htmx:beforeSwap` en `layout.ejs`; htmx 1.x no reemplaza ante 4xx). `showStep` inicializa la sesión (con `saveUninitialized: false`, los primeros auto-saves simultáneos se pisaban).
  - Los rasgos de personaje son una sola lista con ancla YAML (`&character_traits`). `width: half` pone campos contiguos en la misma fila desde `lg`.
  - La sesión guarda IDs limpios (`mapWizardToCore` manda `genero`/`subgenero`/`tono`/`narrator_config`); la rehidratación acepta también el formato legado `"id: Etiqueta"`.
  - Tipos de regla = `RuleType` del dominio (`psicologica`, `entorno`, `fenomeno`, `indicador`); legado del wizard: `paranormal`→`fenomeno`, `social`→`entorno`, `evento`→sin tipo.
  - Se pueden editar historias ya generadas (lo generado se conserva; hay que regenerar para verlo reflejado); con un job activo, `PATCH` → 409.
- **Galería (Spec-311 + Spec-312):** lista variantes de `generated_narrative` por relato + delete con confirmación HTMX.
- **Exportar para el TTS (Spec-490):** «Descargar .md» en el panel de cada variante (`relato_panel.ejs`, `hx-boost="false"`) baja el relato en el formato que lee `audiogen` (proyecto TTS del usuario): `# título`, `## Acto N`, un párrafo por línea y `[pause=1500]` entre actos. `narrative_script_formatter.py` quita lo que `audiogen` saltearía en silencio (líneas que empiezan con `#`/`-`/`*`/`>`: guion de diálogo → raya, énfasis, citas, separadores); el contrato está en `test_narrative_script_audiogen_contract.py`. «Copiar Relato» copia solo los `[data-copy-part]` (rótulos y prosa, sin botones).

## Environment Variables

```
ENV=dev
API_HOST=0.0.0.0:8020
ANTHROPIC_API_KEY=...                              # solo si perfil usa Anthropic
DATABASE_URL=sqlite+aiosqlite:///data/dev/stories.db
PROMPTS_DIR=./config/prompts_generation
BEATS_DEFINITION_FILE=config/llm_beats_definition.yaml
# LLM_PROFILE=ollama-gemma3-12b                    # opcional: pisa active_profile
```

`frontend/.env` independiente (dev): `PORT=3010`, `CORE_API_URL=http://localhost:8020`.

## Database

SQLite vía `aiosqlite`. `init_db()` en `src/infrastructure/database/connection.py` define el esquema. **Quince tablas** (Spec-190 + Spec-460 + Spec-440 + Spec-450):

- `genre`: id, label, order_index — catálogo sembrado por `init_db()` desde `src/infrastructure/database/seeds/genre_catalog.py` (idempotente)
- `subgenre`: genre_id, id, label, order_index — PK compuesta (`otro` existe en cada género)
- `entity_nature`: id, label, order_index — catálogo de naturalezas de entidad; seed `seeds/entity_natures.py` con **upsert** (el seed manda: una etiqueta editada llega a las bases existentes)
- `genre_entity_nature`: genre_id, nature_id — qué naturalezas admite cada género (`desconocida` en todos); el seed solo agrega pares
- `story`: id, title, protagonista, relator, sinopsis, genero, subgenero, tono, narrator_config (JSON), status, created_at — FK `genero` → `genre` y FK compuesta `(genero, subgenero)` → `subgenre`; par inválido → 422 (`ensure_valid_genre`)
- `character`: id, story_id, name, role, traits (JSON), order_index
- `rule`: id, story_id, content, type, intensity, applies_to_beat
- `macro_beat`: id, story_id, number, summary, synopsis_beat, generated_act, status, active_scenario_id, active_scenario_description, system_prompt, user_prompt, type
- `scenario`: id, story_id, order_index, name, description
- `narrative_anchors`: id, story_id, resonance_hamartia, resonance_hybris, resonance_anagnorisis, resonance_peripeteia, resonance_residual
- `narrative_journal`: id, story_id, beat_number, last_events, unresolved_mysteries, physical_emotional_state
- `generated_narrative`: id, story_template_id, title, content, status
- `entity`: id, story_id, order_index (0 = principal), name, nature_id, description, manifestations, limits, reveal_level — máx. 3 por historia; se reescribe con los datos de entrada
- `entity_journal`: id, story_id, beat_number, entity_state — cuelga de `story` (no de `entity`) para sobrevivir a las ediciones
- `generation_job`: id, story_id, kind (`full_generation`|`regenerate_voz`), status, stage, beat, total_beats, params (JSON), error, narrative_id, created_at, started_at, finished_at — índice único parcial: 1 job activo por historia

Repos en `src/infrastructure/database/repositories/`: `SQLStoryRepository`, `SQLBeatRepository`, `SQLGeneratedNarrativeRepository`, `SQLJobRepository`, `SQLGenreRepository`.

## CLI Commands

```bash
uv run python -m src generate --input <yaml> [--mock] [--debug] [--hasta <checkpoint>]
uv run python -m src generate --story-id <uuid>           # retoma historia
uv run python -m src narrate --story-id <uuid> --beats 1,2,3
uv run python -m src export-yaml <story_id>               # round-trip Story → YAML
uv run python -m src export-yaml --all --output-dir <dir> # todas las historias
uv run python -m src import-yaml <archivos...> [--descartar-subgenero-invalido]
                                                          # crea borradores, sin generar
```

Checkpoints `--hasta` (Spec-040): `analyst`, `mapper:1..5`, `voz:1..5`, `journal:1..5`.

## API Endpoints (FastAPI, prefijo `/api/v1`)

- `story_router` — CRUD `/stories` (`PATCH /stories/{id}` edita también generadas; 409 con job activo; 422 si el par género/subgénero no existe o las entidades son inválidas: más de 3, campo largo o naturaleza de otro género), PATCH `status` y `file-path`.
- `catalog_router` (Spec-440, Spec-450) — `GET /catalog/genres` (géneros con sus subgéneros y sus `entity_natures`, ordenados).
- `beat_router` — `GET/PUT /stories/{id}/beats[/{n}]`.
- `job_router` (Spec-460) — `POST /stories/{id}/jobs` (`full_generation` | `regenerate_voz` {beat, narrative_id}; 202/409), `GET /stories/{id}/jobs/active`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `GET /jobs/{id}/events` (SSE de detalle).
- `events_router` (Spec-460) — `GET /events` (SSE global: `snapshot` + `job_*` + heartbeat).
- `narrative_router` (Spec-300) — `/story-templates/{id}/narratives`, `/generated-narratives/{id}` (GET/DELETE/text), `/generated-narratives/{id}/export.md` (Spec-490: descarga para el TTS).
- `stream_router` (Spec-210) — `GET /stories/{id}/stream` (SSE de **solo lectura**: se ata al job activo o reproduce los beats), `/full`, `/health`, `/config/active-profile`.

## Specs

Las specs autoritativas están en `specs/`. Lectura obligatoria al abordar una feature: el SessionStart hook lista los archivos disponibles. Nombres clave: `010_marco_sdd.md` (convenciones), `180_saneamiento_architectural_narrativo.md` (pipeline), `210_arquitectura_web_y_streaming.md` (SSE), `460_jobs_asincronos_y_bus_sse.md` (jobs + bus de eventos), `440_wizard_compacto_generos_anidados.md` (catálogo de géneros + wizard), `450_entidad_narrativa.md` (entidades / la amenaza), `490_exportar_relato_para_tts.md` (export .md para `audiogen`), `500_clean_code_responsability.md` (smells acumulados del core).
