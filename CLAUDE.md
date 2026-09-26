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
make deploy-check  # valida el pase a prod sin tocar nada
make deploy        # pase a prod (Spec-520): solo desde main limpio y al día, sin jobs en curso;
                   # backup de data/prod/stories.db + build de imágenes + verificación
```

**Producción cambia solo con `make deploy`.** Los contenedores (`narrative-api` :8010, `narrative-ui` :3000, nginx `storymaker.test`) llevan el código **y `config/`** dentro de la imagen: cambiar de rama o editar prompts en el directorio de trabajo no los afecta. Datos (`data/prod/`) y secretos (`.env.prod`) quedan afuera.

## Architecture

Clean Architecture con cuatro capas + cli + core:

```
domain/          → Entities (Story, Direction, WorkshopItem, ActOutline, MacroBeat…),
                   Interfaces (LLMProvider), DTOs streaming, exceptions
application/     → Use Cases (Director, Voz, RegenerateBeatVoz…) + Services
                   (authoring/: Consultor, Planificador, Verificador, OutlineNarrator;
                   PromptBuilder, StreamingService, JobManager, EventBus, repetition_check)
infrastructure/  → Adapters (Ollama/Anthropic/Gemini/Mock/RoleRouting) + SQLite repos +
                   ResponseNormalizer + YamlStoryLoader/Exporter + CLIContainer (DI)
presentation/    → FastAPI routers (story, authoring, beat, narrative, stream, job, events,
                   catalog) + Pydantic schemas + runtime.py (singletons JobManager/EventBus)
core/            → StoryRunner orchestrator
cli/             → CLI runner, commands, logger, progress reporter
```

Entry points: `src/main.py` (FastAPI) y `src/__main__.py` (CLI vía `python -m src`).

## Core Concept: el relato sale de la escaleta (Spec-530)

El autor arma la historia en el **asistente**: Dirección → Taller (preguntas de la IA) → Escaleta (5 actos). Las historias se narran en **5 actos** (estructura en `config/llm_beats_definition.yaml`: nombre, intención, intensidad, reglas de revelación y exposición de la amenaza por acto).

**La IA nunca corre sola:** cada llamada es un comando explícito del usuario (job) y la página se bloquea con un modal hasta que termina.

| Rol | Componente | Cuándo | Responsabilidad |
|---|---|---|---|
| Consultor | `WorkshopConsultant` | 1 por ronda del taller (job `consult`) | Evalúa los criterios de `config/workshop_criteria.yaml` y hace preguntas con opciones; lo respondido e «intencional» vuelve en la ronda siguiente |
| Planificador | `OutlinePlanner` | job `plan_outline`, o al generar sin escaleta | Arma la escaleta: objetivo, hechos, cambio, escenario, en escena, lo que se guarda, siembras/cobros, decisiones |
| Verificador | `OutlineVerifier` | después de planificar (job `verify_outline`) | Ubica las decisiones del autor, fuerza el final intencional en el acto 5, avisos por acto (máx. 3) |
| Voz | `OutlineNarrator.voice_prompts` + `VozUseCase.narrate_with_prompts` | 1 por acto | Prosa del acto desde la escaleta |
| Memoria | `OutlineNarrator.remember` | 1 por acto | Hechos acumulados («Acto N: …»), estado y `used_motifs` (hasta 30, llegan a la Voz como «ya usado, no repetir») |

Generar un relato: **10 llamadas** con escaleta; 12 si la historia no la tiene (entró por `import-yaml`): primero se arma y se guarda.

La Voz recibe: quién narra y cómo lo cuenta (`direction.telling` → `config/authoring_options.yaml`), la guía de oficio, el acto (objetivo, hechos, cambio, lo que no se revela), el escenario, las reglas del acto (`rule.applies_to_beat`), la amenaza según la exposición del acto, solo los personajes en escena (con su parentesco), la memoria y lo ya usado. Extensión proporcional a los hechos del acto.

### Entidades — la amenaza (Spec-450)

- Opcionales, hasta 3 por historia (`Story.entities`); la primera es la **principal**. Cada una: nombre, naturaleza (catálogo filtrado por género), descripción, manifestaciones, límites y `reveal_level` (`nunca` | `insinuada` | `progresiva` | `explicita`). El asistente carga la principal en la Dirección.
- `config/llm_beats_definition.yaml`: `entity_exposure` por acto → vocabulario `entity_exposures` (`show` = campos de la ficha que ve la Voz, `guide` = instrucción). Con «señales» la Voz no ve ni nombre ni naturaleza (`OutlineNarrator._threat_lines`).
- Snapshot de los prompts del pipeline: `tests/fixtures/snapshots/pipeline_prompts.json` (`SNAPSHOT_UPDATE=1` para regenerarlo a propósito).

### Control de repetición (Spec-530 §8.3)

`repetition_check.py`, determinístico: frases repetidas de actos anteriores, clichés por raíz (`voice_cliches.txt`) y nombres inventados (fuera del elenco). Se muestra en el panel del relato (`GET /generated-narratives/{id}/repetition`); no regenera solo.

## Data Flow

```
Asistente (/nuevo → /asistente/{id}/direccion|taller|escaleta)
  PUT direction · PATCH workshop/{criterio} · PUT outline/{n}   (autoguardado)
  jobs consult | plan_outline | verify_outline                   (comandos explícitos)
       ↓
  POST /stories/{id}/jobs (full_generation) → DirectorUseCase.execute_full():
    [0] sin escaleta completa → Planificador + Verificador → story_repo.save_outline()
    Para cada acto 1..5:
      OutlineNarrator.voice_prompts()   → prompts (sin LLM)
      VozUseCase.narrate_with_prompts() → MacroBeat.generated_act (1 LLM)
      OutlineNarrator.remember()        → narrative_journal (1 LLM)
       ↓
  consolidación → GenerateNarrativesUseCase.consolidate_and_save()
               → generated_narrative (variante UUID)
```

En la web corre como **job** (Spec-460): `JobManager` lanza una `asyncio.Task` independiente de la conexión que consume `stream_story()` (`streaming_service.py`). `stream_story` traduce el pipeline a eventos (`status` con `stage` ∈ `planificador`/`verificador`/`voz`/`journal`/`consolidando`, `beat`, `total_beats`; `beat_start`, `beat_done`, `heartbeat`, `done`, `stream_error`), tras el último acto consolida y enriquece `done` con `narrative_id`. Heartbeat cada 15s.

## LLM Provider Abstraction

Protocolo `LLMProvider` (`src/domain/interfaces.py`). Adapters en `src/infrastructure/adapters/`: `OllamaAdapter`, `AnthropicAdapter`, `GeminiCLIAdapter`, `MockLLMAdapter` (tests, `--mock`) y `RoleRoutingAdapter`.

Provider activo: definido en perfil del YAML. Override: `LLM_PROVIDER` env o `--provider` CLI.

**Proveedor por rol (Spec-480):** un rol puede declarar `provider` en el perfil (`roles.voz.provider: anthropic`); si no, usa el del perfil. Con un solo proveedor `LLMFactory` devuelve el adapter de siempre; si los roles mezclan proveedores, un `RoleRoutingAdapter` despacha cada llamada al adapter de su rol (todas pasan `role`). `/health` verifica cada proveedor en uso y `/config/active-profile` muestra el de cada rol.

**Salida estructurada (Spec-530):** `LLMProvider.generate(response_schema=…)` — Ollama lo manda como `format`, Anthropic como `output_config.format` (`anthropic_json_schema()`). `generate_structured()` valida con Pydantic, reintenta una vez y si no, `LLMStructuredOutputError`. El mock responde con `mock_structured.py`.

**`AnthropicAdapter`:** sin `temperature` para los modelos que no la aceptan (Sonnet 5, Opus 5, Opus 4.7/4.8, Fable); `thinking` por rol (`adaptive` / `disabled` — en Sonnet 5 / Opus 5 omitirlo **piensa**); `effort` en `output_config`; `max_tokens` = `num_predict` con piso 16000 si piensa; texto de los bloques `text`; `refusal` → `LLMRefusalError`, `max_tokens` → error; `LLMResponse.input_tokens/output_tokens`. Tests con `tests/support/fake_anthropic.py` (tipos reales del SDK, sin llamadas).

## LLM Configuration

**Fuente de verdad: `config/llm_core_definitions.yaml`.** Contiene perfiles (provider + roles), filtros de respuesta y overrides por modelo. El `.env` solo guarda secretos y override `LLM_PROFILE`.

- Perfiles autocontenidos bajo `profiles:` (cada uno trae provider, bloque adapter y sus roles: `consultor`/`planificador`/`verificador`, `voz`, `journal`; `director` es la base de los tres primeros cuando el perfil no los declara).
- Activación: `active_profile:` en YAML o `LLM_PROFILE=<nombre>` (env tiene precedencia). Resolver en `src/config.py`.
- Convención model-por-rol: el `model` que se envía al LLM vive en `profiles.<perfil>.roles.<rol>.model`.
- Perfil híbrido `ollama-gemma3-12b-voz-sonnet5` (Spec-480): la Voz en `claude-sonnet-5`, el resto en `gemma3:12b`. **No activo**; cuesta ~US$ 0,08 por relato (~US$ 0,13 con `thinking: adaptive`). Evaluarlo con `scripts/evaluate_voice.py --profile ollama-gemma3-12b-voz-sonnet5 --yes` (sin `--yes` solo muestra el costo estimado y no genera).
- **Duración estimada (Spec-510):** `profiles.<perfil>.estimated_seconds: {full_generation, regenerate_voz, consult, plan_outline, verify_outline}` es el valor inicial; con historial manda la mediana de los últimos 5 jobs `done` del mismo tipo y perfil (`JobDurationEstimator`, descarta < 5 s = corridas con el mock). Sin el bloque: 240 / 60 s (`DEFAULT_ESTIMATED_SECONDS`).
- Filtros (`response_filters`, Spec-080): `thinking_tags`, `strip_line_patterns`, `preserve_paragraph_breaks`, `model_overrides` por substring de modelo. Aplicados por `ResponseNormalizer` antes de persistir.

Detalle completo: Spec-060, Spec-070.

## Prompt System

Templates Markdown en `config/prompts_generation/`, cargados por `TemplateLoader`:

- Asistente: `authoring_consultant*.md`, `authoring_planner*.md`, `authoring_verifier*.md`.
- Relato: `outline_voice*.md` (Voz) y `outline_journal*.md` (memoria).
- Oficio de la Voz (Spec-470): `voice_craft.md` (ritmo según la intensidad del acto, sugerir antes que nombrar el miedo, cierre en una imagen, primera persona, léxico) vía `{guia_oficio}`, y el bloque «CÓMO LLAMÁS A CADA PERSONAJE» (`{parentescos}`). La lista de clichés prohibidos vive en `voice_cliches.txt` (una por línea; la usan el prompt y las métricas). `PromptBuilder` quedó como piezas compartidas: `get_beat_info`, `narrator_name`, `_voice_extras`.

**Evaluar:**
- La prosa: `uv run python scripts/evaluate_voice.py --label <nombre> --runs 2 --out <dir> [--mock]` genera «El monte prohibido» con el perfil activo en una DB temporal y mide clichés, parentescos candidatos, nombre del narrador fuera de diálogo y 4-gramas repetidos (`scripts/voice_metrics.py`).
- El asistente: `uv run python scripts/evaluate_workshop.py --runs 2 --out <dir> [--stories pena] [--variants …] [--mock]` compara el camino base con el del asistente (S6; evidencia en `scripts/research/530/`).

## Web & Streaming (Spec-210)

- **Frontend:** Express + EJS + HTMX en `frontend/`. Único origen para el browser. Proxy interno `/api/*` → `CORE_API_URL`.
- **Tema (Spec-531):** un solo tema claro, «Papel». La paleta vive **solo** en `frontend/src/styles/theme.css` (`--forge-*`, importado en `globals.css`) y se usa con las clases `forge-*` de Tailwind, que admiten opacidad (`bg-forge-accent/10`, vía `color-mix`). Estados: `error` / `warning` / `success` / `info`, cada uno con `-bg` y `-border`; además `on-accent` y `overlay`. Nada de colores fijos en vistas, estilos ni JS: lo verifican `no-hardcoded-colors` y `palette-contrast` (AA ≥ 4,5:1). Tipografía: sans en la interfaz, `.prose-forge` (serif, interlineado 1,7) para la prosa. Favicon: vela (`public/favicon.svg`; PNG con `npx ts-node scripts/build-favicons.ts`). Capturas para comparar: `CAPTURAS=<carpeta> npx playwright test visual-snapshots` → `frontend/capturas/531/<carpeta>/`.
- **Jobs (Spec-460):** generar y regenerar un acto son jobs (`generation_job`). `JobManager` (singleton en `src/presentation/runtime.py`) corre cada job como `asyncio.Task`: cerrar la pestaña no lo detiene, `POST /jobs/{id}/cancel` sí. Un solo job activo por historia (lock + índice único parcial) → 409 con el job existente. Al arrancar, los jobs que quedaron activos pasan a `failed` ("interrumpida por reinicio").
- **Eventos (Spec-460):** `EventBus` en memoria con canales `job:<id>` (detalle, lo usa la sala) y `global` (ciclo de vida `job_*`, lo usa todo el resto). Ids por canal → reconexión con `Last-Event-ID`. Ningún GET arranca trabajo.
- **Cliente:** `public/js/event-bus.js` abre 1 `EventSource` global por pestaña (en `<head>`, sobrevive a hx-boost; se cierra en la sala) y re-emite `forge:*` en el DOM. Consumidores: banda de generación, pie (estado del Core), botones `[data-generation-trigger]` (`generation-guard.js`), galería en vivo y paneles atados a un job. Heartbeat 15s no negociable.
- **Asistente de autoría (Spec-530):** «Nuevo relato» → `/nuevo`; la historia se trabaja en `/asistente/{id}/{direccion|taller|escaleta}` (`/generar` redirige ahí; el wizard viejo ya no existe). Toda historia se edita en el asistente, también las importadas (sin dirección, la sinopsis es su «¿de qué trata?»).
  - Autoguardado real desde `public/js/asistente.js` (cola por formulario, `flushAll`) directo a `/api/v1/authoring/*`.
  - La IA solo con comandos explícitos (jobs `consult` / `plan_outline` / `verify_outline`): un modal bloquea la página (`inert`) hasta que el job termina; se reengancha a un job activo al recargar.
  - Los personajes se suman en el acto donde aparecen (`POST …/characters`), no todos al inicio. Las reglas se cargan dentro de un acto (`applies_to_beat`).
  - La escaleta es editable; los avisos del Verificador se ven y se descartan por acto; un acto queda «a revisar» si cambió la dirección.
  - Round-trip YAML con `python -m src export-yaml` / `import-yaml`: exporta dirección, taller y escaleta; importa también los YAML viejos (ignora `tono`, `traits`, `rule.type` y las claves viejas del narrador).
- **Galería (Spec-311 + Spec-312):** lista variantes de `generated_narrative` por relato + delete con confirmación HTMX.
- **Exportar para el TTS (Spec-490):** «Descargar .md» en el panel de cada variante (`relato_panel.ejs`, `hx-boost="false"`) baja el relato en el formato que lee `audiogen` (proyecto TTS del usuario): `# título`, `## Acto N`, un párrafo por línea y `[pause=1500]` entre actos. `narrative_script_formatter.py` quita lo que `audiogen` saltearía en silencio (líneas que empiezan con `#`/`-`/`*`/`>`: guion de diálogo → raya, énfasis, citas, separadores); el contrato está en `test_narrative_script_audiogen_contract.py`. «Copiar Relato» copia solo los `[data-copy-part]` (rótulos y prosa, sin botones).
- **Tiempo estimado (Spec-510):** cada job guarda en `params` su `profile` y `estimated_seconds`; el payload y `JobResponse` traen `started_at`, `finished_at` y `elapsed_seconds`. `public/js/eta.js` (`window.ForgeEta`, UMD testeable en Vitest) calcula avance y tiempo restante (mezcla la estimación con el ritmo real; redondeado, nunca negativo: «tardando más de lo habitual»); lo usan el banner y la sala (tick de 15 s; `event-bus.js` marca `received_at` para no depender del reloj del Core). Antes de lanzar, el middleware `loadEstimates` (solo galería, ficha, sala y relatos; timeout 1,5 s) deja «≈ N min» en `res.locals.estimateLabels` → partial `estimate.ejs`, confirmación de la sala y `hx-confirm` de regenerar un acto.

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

SQLite vía `aiosqlite`. `init_db()` en `src/infrastructure/database/connection.py` define el esquema. **Quince tablas:**

- `genre`: id, label, order_index — catálogo sembrado por `init_db()` desde `src/infrastructure/database/seeds/genre_catalog.py` (idempotente)
- `subgenre`: genre_id, id, label, order_index — PK compuesta (`otro` existe en cada género)
- `entity_nature`: id, label, order_index — catálogo de naturalezas de entidad; seed `seeds/entity_natures.py` con **upsert** (el seed manda: una etiqueta editada llega a las bases existentes)
- `genre_entity_nature`: genre_id, nature_id — qué naturalezas admite cada género (`desconocida` en todos); el seed solo agrega pares
- `story`: id, title, protagonista, relator, sinopsis, genero, subgenero, narrator_config (JSON: `storyteller_id`, `storyteller_name`, `voice {person, tense}`), direction (JSON: premisa, efecto, final, final intencional, cómo lo cuenta), status, created_at — FK `genero` → `genre` y FK compuesta `(genero, subgenero)` → `subgenre`; par inválido → 422 (`ensure_valid_genre`). `Story.atmosfera` = «género (subgénero)».
- `character`: id, story_id, name, role, kind (`persona`|`sin_nombre`|`grupo`), relation (qué es para quien narra), order_index
- `rule`: id, story_id, content, applies_to_beat (NULL = global)
- `macro_beat`: id, story_id, number, summary, synopsis_beat, generated_act, status, active_scenario_id, active_scenario_description, system_prompt, user_prompt, type — la salida de cada acto
- `scenario`: id, story_id, order_index, name, description
- `narrative_journal`: id, story_id, beat_number, last_events, physical_emotional_state, used_motifs (JSON)
- `generated_narrative`: id, story_template_id, title, content, status
- `entity`: id, story_id, order_index (0 = principal), name, nature_id, description, manifestations, limits, reveal_level — máx. 3 por historia; se reescribe con los datos de entrada
- `story_workshop`: story_id, level (`direccion`|`escaleta`), criterion, status (`cumple`|`parcial`|`falta`|`intencional`), question, options (JSON), answer, round, asked (JSON) — único por (story_id, level, criterion)
- `act_outline`: la escaleta, entrada de cada acto (separada de `macro_beat`, que es la salida): story_id, number 1–5, goal, events, change_from/to, scenario y on_stage (por nombre), held_back, seeds, payoffs, decisions, warnings, needs_review
- `generation_job`: id, story_id, kind (`full_generation`|`regenerate_voz`|`consult`|`plan_outline`|`verify_outline`), status, stage, beat, total_beats, params (JSON), error, narrative_id, created_at, started_at, finished_at — índice único parcial: 1 job activo por historia

Repos en `src/infrastructure/database/repositories/`: `SQLStoryRepository`, `SQLBeatRepository`, `SQLGeneratedNarrativeRepository`, `SQLJobRepository`, `SQLGenreRepository`.

**Cambio de esquema en prod:** sin migraciones. `export-yaml --all` con el código que está en prod (la DB vieja no tiene las columnas nuevas), DB nueva, `import-yaml` con el código nuevo. Las historias vuelven como borradores.

## CLI Commands

```bash
uv run python -m src generate --input <yaml> [--mock] [--debug]   # respeta dirección y escaleta del YAML
uv run python -m src generate --story-id <uuid>           # regenera una historia existente
uv run python -m src export-yaml <story_id>               # round-trip Story → YAML
uv run python -m src export-yaml --all --output-dir <dir> # todas las historias
uv run python -m src import-yaml <archivos...> [--descartar-subgenero-invalido]
                                                          # crea borradores, sin generar
```

## API Endpoints (FastAPI, prefijo `/api/v1`)

- `story_router` — CRUD `/stories` (`PATCH /stories/{id}` edita también generadas; 409 con job activo; 422 si el par género/subgénero no existe o las entidades son inválidas: más de 3, campo largo o naturaleza de otro género), PATCH `status` y `file-path`. `GET /stories/{id}` trae `storyteller_config` (vista de la ficha) y `authoring`.
- `catalog_router` (Spec-440, Spec-450) — `GET /catalog/genres` (géneros con sus subgéneros y sus `entity_natures`, ordenados).
- `authoring_router` (Spec-530) — `/authoring/options`, `POST /authoring/stories`, `GET /authoring/stories/{id}` (estado de Dirección/Taller/Escaleta), `PUT …/direction`, `PATCH …/workshop/{criterio}` (`answer`|`decide`|`intentional`|`reopen`), `PUT …/outline/{n}`, `POST …/outline/{n}/warnings/dismiss`, `POST …/characters`; 409 (con `X-Job-Id`) si hay un job activo. La IA corre como jobs `consult` | `plan_outline` | `verify_outline` (`POST /stories/{id}/jobs`).
- `beat_router` — `GET/PUT /stories/{id}/beats[/{n}]`.
- `job_router` (Spec-460) — `POST /stories/{id}/jobs` (`full_generation` | `regenerate_voz` {beat, narrative_id} | `consult` | `plan_outline` | `verify_outline`; 202/409/422), `GET /stories/{id}/jobs/active`, `GET /jobs/{id}`, `GET /jobs/estimates` (Spec-510), `POST /jobs/{id}/cancel`, `GET /jobs/{id}/events` (SSE de detalle).
- `events_router` (Spec-460) — `GET /events` (SSE global: `snapshot` + `job_*` + heartbeat).
- `narrative_router` (Spec-300) — `/story-templates/{id}/narratives`, `/generated-narratives/{id}` (GET/DELETE/text), `/generated-narratives/{id}/export.md` (Spec-490: descarga para el TTS), `/generated-narratives/{id}/repetition` (Spec-530: control de repetición).
- `stream_router` (Spec-210) — `GET /stories/{id}/stream` (SSE de **solo lectura**: se ata al job activo o reproduce los beats), `/full`, `/health`, `/config/active-profile`.

## Specs

Las specs autoritativas están en `specs/`. Lectura obligatoria al abordar una feature: el SessionStart hook lista los archivos disponibles. Nombres clave: `010_marco_sdd.md` (convenciones), `530_asistente_autoria_y_escaleta.md` (asistente, escaleta y pipeline actual; reemplaza al de la 180 y al wizard de la 220/440), `210_arquitectura_web_y_streaming.md` (SSE), `460_jobs_asincronos_y_bus_sse.md` (jobs + bus de eventos), `440_wizard_compacto_generos_anidados.md` (catálogo de géneros), `450_entidad_narrativa.md` (entidades / la amenaza), `490_exportar_relato_para_tts.md` (export .md para `audiogen`), `510_tiempo_estimado_generacion.md` (tiempo estimado de los jobs), `520_deploy_desde_imagen.md` (pase a producción), `531_tema_claro_y_favicon.md` (tema único y favicon).
