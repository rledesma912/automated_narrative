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
make dev-up      # dev siempre levantado (Spec-540): contenedores narrative-dev, API :8040, UI :3040
make dev-status  # rama, commit, contenedores, /health y UI en modo dev (≠ 0 si algo falla)
make dev-logs    # últimas líneas de api y ui de dev
make dev-rebuild # reconstruye las imágenes de dev (tras cambiar pyproject.toml / package.json)
make dev-down    # baja dev
make dev-db      # recrea data/dev/stories.db vacía con los catálogos y la verifica
                 # (si tiene historias pide ARGS=--yes; make db = alias)
make api / ui / dev  # dev a mano en la terminal, mismos puertos (antes make dev-down)
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

**Producción cambia solo con `make deploy`.** Los contenedores (`narrative-api` :8010, `narrative-ui` :3000, nginx `storymaker.prd` y `http://192.168.0.65`) llevan el código **y `config/`** dentro de la imagen: cambiar de rama o editar prompts en el directorio de trabajo no los afecta. Datos (`data/prod/`) y secretos (`.env.prod`) quedan afuera.

**Dev siempre publicado en `storymaker.test` (Spec-540).** `docker-compose.dev.yml` (proyecto `narrative-dev`, aparte del de prod): `narrative-api-dev` :8040 y `narrative-ui-dev` :3040, con el código del directorio de trabajo **montado** (la rama activa, con sus cambios sin commitear), `restart: unless-stopped`, datos de `data/dev/` y `.env`. uvicorn (`src/`, `config/*.yaml`) y nodemon + `tailwind --watch` recargan solos; las vistas `.ejs` y los prompts se leen en cada request/generación. Dependencias nuevas → `make dev-rebuild`; esquema nuevo → `make dev-db`. Una recarga de uvicorn interrumpe un job de dev en curso. El proxy (`/mnt/LLM/apps/reverse_proxy/nginx_config/default.conf`, fuera del repo) manda `storymaker.test` → :3040 y `storymaker.prd` + la IP (`default_server`) → prod :3000.

**Cierre de cada checkpoint (Spec-540 §2.5):** tests en verde **y** dev reflejando el cambio (`make dev-status` en verde; antes `make dev-rebuild` / `make dev-db` si hace falta). Al usuario: la URL exacta en `https://storymaker.test` y qué mirar para validar.

## Architecture

Clean Architecture con cuatro capas + cli + core:

```
domain/          → Entities (Story, Direction, WorkshopItem, ActOutline (entrada del acto), ActText (salida: su prosa)…),
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

**Máxima del pipeline (2026-09-27):** la Voz recibe un arnés **simple y asertivo**: la escaleta del acto, la memoria y listas cortas de «no repetir»; nunca reglas de continuidad para resolver mientras escribe. Lo conceptual —continuidad, tiempo, lugares, personajes, qué se revela— se resuelve **antes**, en la escaleta: análisis de la IA (Consultor, Planificador, Verificador) y confirmación del autor en la UI (taller y escaleta). Lo que solo aparece en la prosa (repeticiones, clichés, nombres inventados) se **detecta después** y se muestra; **nunca se corrige solo**. Cada campo o chequeo nuevo tiene que prevenir un error que se vio de verdad (para no volver al formulario gigante).

**La IA nunca corre sola:** cada llamada es un comando explícito del usuario (job) y la página se bloquea con un modal hasta que termina.

| Rol | Componente | Cuándo | Responsabilidad |
|---|---|---|---|
| Consultor | `WorkshopConsultant` | 1 por ronda del taller (job `consult`) | Evalúa los criterios de `config/workshop_criteria.yaml` y hace preguntas con opciones; lo respondido e «intencional» vuelve en la ronda siguiente |
| Planificador | `OutlinePlanner` | job `plan_outline`, o al generar sin escaleta | Arma la escaleta: «cómo llega acá» (actos 2–5), objetivo, hechos, cambio, escenario, en escena, lo que todavía no se cuenta y en qué acto se revela, siembras/cobros, decisiones. Recibe la receta del efecto (Spec-560 A5), la sinopsis por acto de los YAML viejos como guía (Spec-570 D2) y, al rearmar, los avisos visibles de la escaleta anterior (A6) y las reglas que el autor ancló a cada acto (Spec-630) |
| Verificador | `OutlineVerifier` | después de planificar (job `verify_outline`) | Ubica las decisiones del autor, fuerza el final intencional en el acto 5, avisos por acto (máx. 3 visibles): reglas (`sin_hechos`, `sin_cambio`, `sin_puente`, `sin_revelacion`, elenco, siembras) y de la IA (hechos repetidos o adelantados, secretos sin revelar, continuidad entre actos, receta del efecto). Respeta los ignorados (Spec-550 H10). Ve, por acto, quiénes están, cómo cambia y sus reglas, y marca primero un hecho que contradice una regla del acto (Spec-630) |
| Voz | `OutlineNarrator.voice_prompts` + `VozUseCase.narrate_with_prompts` | 1 por acto | Prosa del acto desde la escaleta. Abre con el puente y sigue desde el último párrafo del acto anterior (Spec-560 A1, Spec-590). Oraciones completas, sin diálogo directo (Spec-590) |
| Memoria | `OutlineNarrator.remember` | 1 por acto | Hechos acumulados («Acto N: …»), estado, `body_state` (el cuerpo: heridas, cansancio), `narrator_traits` (rasgos que inventó la Voz, hasta 12) y `used_motifs` (hasta 30, llegan a la Voz como «ya usado, no repetir»). Recibe la memoria anterior completa (Spec-590 E) |
| Guion | `VideoScriptService` (rol `guion`, Sonnet 5.5) | job `video_script`, 1 por paquete (+1 reintento si no pasa los chequeos) | Spec-610: reparte el relato en bloques de lectura (rangos de párrafos, nunca texto), indicaciones, énfasis, pausas; momentos de pantalla con prompts de imagen y movimiento; intro y outro de la calabaza. `VideoScriptBuilder` chequea sin IA (cobertura por acto, énfasis que existen, 10–15 momentos, palabras prohibidas, «Buenas noches», largos) |

Generar un relato: **10 llamadas** con escaleta; 12 si la historia no la tiene o solo tiene borradores (entró por `import-yaml`): primero se arma y se guarda. Regenerar un acto: **2 llamadas** (Voz + Memoria del acto, Spec-560 A2); los actos siguientes quedan marcados como escritos con la versión anterior (`macro_beat.stale`, aviso en el panel).

La Voz recibe: quién narra y cómo lo cuenta (`direction.telling` → `config/authoring_options.yaml`), la guía de oficio, el acto (objetivo, hechos, cambio, lo que no se revela), el escenario, las reglas del acto (`rule.applies_to_beat`), la amenaza según la exposición del acto, solo los personajes en escena (con su parentesco) y lo ya usado (sin los motivos que están en los hechos del acto o en la ficha de la amenaza, `_motifs_for`); además (Spec-560) «CÓMO SE LLEGA A ESTE ACTO», «ASÍ TERMINÓ EL ACTO ANTERIOR» (su último párrafo, tope 120 palabras, Spec-590) y, si ya hubo un relato o se regenera, «EN LA VERSIÓN ANTERIOR DE ESTE ACTO PASÓ ESTO» (lo que marcó el control de repetición: `repetition_check.last_version_findings`). Spec-590 suma: «LA HISTORIA, PARA QUE CONOZCAS A …» (solo la **primera oración** de la premisa o la sinopsis: la completa adelantaba hechos), «LO QUE YA PASÓ» desde los hechos de la escaleta de los actos anteriores (cae a la memoria si no hay), «CÓMO ESTÁ … AHORA» (`body_state` + estado) y «ASÍ ES …» (`narrator_traits`). La personalidad del narrador la inventa la Voz (gestos chicos que no cambian lo que pasa) y la Memoria la sostiene; no hay ficha del protagonista. Extensión proporcional a los hechos del acto: 250–500 palabras (`word_range`, desenlace 180–300), un párrafo por evento: ~2 000 palabras, un episodio de ~15 min leído en voz alta (Spec-610 D11).

### Entidades — la amenaza (Spec-450)

- Opcionales, hasta 3 por historia (`Story.entities`); la primera es la **principal**. Cada una: nombre, naturaleza (catálogo filtrado por género), descripción, manifestaciones, límites y `reveal_level` (`nunca` | `insinuada` | `progresiva` | `explicita`). El asistente carga la principal en la Dirección.
- `config/llm_beats_definition.yaml`: `entity_exposure` por acto → vocabulario `entity_exposures` (`show` = campos de la ficha que ve la Voz, `guide` = instrucción). Con «señales» la Voz no ve ni nombre ni naturaleza (`OutlineNarrator._threat_lines`).
- Snapshots de los prompts: `tests/fixtures/snapshots/{pipeline,voice,assistant}_prompts.json` (`SNAPSHOT_UPDATE=1` para regenerarlos a propósito; ver «Prompt System»).

### Control de repetición (Spec-530 §8.3)

`repetition_check.py`, determinístico: frases repetidas de actos anteriores, clichés por raíz (`voice_cliches.txt`), nombres inventados (fuera del elenco) y, desde la Spec-590, **oraciones cortadas** (menos de 5 palabras o sin verbo conjugado; aviso desde el 25 % del acto, con hasta 3 ejemplos) y **diálogo** (líneas con raya o tramos entre comillas); desde la Spec-640, **comparaciones** («como si…», «como un/una…»; aviso desde la segunda del acto, con hasta 3 ejemplos). Al regenerar un acto, lo que marcó vuelve a la Voz (`_avoid`). Se muestra en el panel del relato (`GET /generated-narratives/{id}/repetition`); no regenera solo.

## Data Flow

```
Asistente (/nuevo → /asistente/{id}/direccion|taller|escaleta)
  PUT direction · PATCH workshop/{criterio} · PUT outline/{n}   (autoguardado)
  jobs consult | plan_outline | verify_outline                   (comandos explícitos)
       ↓
  POST /stories/{id}/jobs (full_generation) → GenerateStoryUseCase.execute_full():
    [0] sin escaleta completa → Planificador + Verificador → story_repo.save_outline()
    Para cada acto 1..5:
      OutlineNarrator.voice_prompts()   → prompts (sin LLM)
      VozUseCase.narrate_with_prompts() → ActText.generated_act (1 LLM)
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

**`AnthropicAdapter`:** sin `temperature` para los modelos que no la aceptan (Sonnet 5 / 5.5, Opus 5, Opus 4.7/4.8, Fable); `thinking` por rol (`adaptive` / `disabled` / `between_tools` — en Sonnet 5 / 5.5 y Opus 5 omitirlo **piensa**; Sonnet 5.5 rechaza `disabled`: sin pensar es `between_tools`); `effort` en `output_config`; `max_tokens` = `num_predict` con piso 16000 si piensa; texto de los bloques `text`; `refusal` → `LLMRefusalError`, `max_tokens` → error; si la API no atiende (sin crédito, clave, 429/529/5xx, sin red) → `LLMUnavailableError` con un mensaje coloquial que llega tal cual a `job.error`, sin reintento ni caída al modelo local (Spec-600 D3); `LLMResponse.input_tokens/output_tokens`. Tests con `tests/support/fake_anthropic.py` (tipos reales del SDK, sin llamadas).

## LLM Configuration

**Fuente de verdad: `config/llm_core_definitions.yaml`.** Contiene perfiles (provider + roles), filtros de respuesta y overrides por modelo. El `.env` solo guarda secretos y override `LLM_PROFILE`.

- Perfiles autocontenidos bajo `profiles:` (cada uno trae provider, bloque adapter y sus roles: `consultor`/`planificador`/`verificador`, `voz`, `journal`, `guion`; `director` es la base de los tres primeros cuando el perfil no los declara).
- Activación: `active_profile:` en YAML o `LLM_PROFILE=<nombre>` (env tiene precedencia). Resolver en `src/config.py`.
- Convención model-por-rol: el `model` que se envía al LLM vive en `profiles.<perfil>.roles.<rol>.model`.
- **Rol `guion` (Spec-610, D3):** Sonnet 5.5 en `hibrido-sonnet55` y `anthropic-sonnet55` (adaptativo, effort `low`); gemma con `num_ctx` 16384 en el local, solo para probar. `evaluate_voice.py` no lo cuenta en el costo de un relato.
- **Tres perfiles (Spec-600, 2026-09-30):** `ollama-gemma3-12b` (todos los roles locales; `active_profile` del YAML), `hibrido-sonnet55` (**la Voz en Claude Sonnet 5.5**, adaptativo con effort `low`; el resto igual que gemma; **activo en dev y prod** con `LLM_PROFILE` en `.env` / `.env.prod`; ~US$ 0,09 por relato, medido en la Spec-600 §7) y `anthropic-sonnet55` (todo en Claude, no activo: para comparar o mover otro rol). Mezclar proveedores por rol es `provider` en el rol (`RoleRoutingAdapter`). Evaluar con costo: `scripts/evaluate_voice.py --profile hibrido-sonnet55 --yes` (sin `--yes` solo estima). La clave de la API vive en `.env` / `.env.prod` y **vence el 2026-10-30**.
- **Duración estimada (Spec-510):** `profiles.<perfil>.estimated_seconds: {full_generation, regenerate_voz, consult, plan_outline, verify_outline, video_script}` es el valor inicial; con historial manda la mediana de los últimos 5 jobs `done` del mismo tipo y perfil (`JobDurationEstimator`, descarta < 5 s = corridas con el mock). Sin el bloque: 240 / 60 s (`DEFAULT_ESTIMATED_SECONDS`).
- Filtros (`response_filters`, Spec-080): `thinking_tags`, `strip_line_patterns`, `preserve_paragraph_breaks`, `model_overrides` por substring de modelo. Aplicados por `ResponseNormalizer` antes de persistir.

Detalle completo: Spec-060, Spec-070.

## Prompt System

**Regla (Spec-620): ningún texto que lee un LLM ni ningún mensaje que ve una persona se escribe en Python.** El código decide qué sección va y con qué datos; el texto vive en `config/`. Lo verifica `tests/unit/test_prompts_fuera_del_codigo.py` (recorre `src/` con `ast`; lo técnico va a `PERMITIDOS` con su motivo).

Templates Markdown en `config/prompts_generation/`, cargados por `TemplateLoader`:

- Asistente: `authoring_consultant*.md`, `authoring_planner*.md`, `authoring_verifier*.md`.
- Relato: `outline_voice*.md` (Voz) y `outline_journal*.md` (memoria).
- Paquete para el video (Spec-610): `video_script*.md`, con fragmentos en `fragments/video/` (los problemas del reintento en `fragments/video/problemas/`).
- **Fragmentos** (`fragments/voz|memoria|asistente|video/`): las secciones que van o no según la historia («CÓMO ESTÁ … AHORA», la amenaza, las decisiones del taller…), con `TemplateLoader.fragment("voz/como_esta", narrador=…)` (`str.format`; error si falta el archivo o un dato). `fragments/README.md` dice qué fragmento llena cada hueco de cada plantilla. Los nombres de los actos que ven la Voz y el Planificador son `label` en `llm_beats_definition.yaml`.
- **Mensajes** para la pantalla: `config/core_messages.yaml` por área (`workshop`, `verifier`, `llm`, `stage`, `job`, `api`, `validacion`, `historia_nueva`, `repeticion`), con `src.messages.message("area.clave", **datos)` (como `src/config.py`, lo usan todas las capas).
- **Snapshots** (sin LLM): `tests/fixtures/snapshots/pipeline_prompts.json` (generación completa), `voice_prompts.json` (la Voz con todas sus secciones), `assistant_prompts.json` (Consultor, Planificador y Verificador) y `video_prompts.json` (el paquete para el video, Spec-610). Cada snapshot nuevo trae un test que falla si una sección deja de aparecer. `SNAPSHOT_UPDATE=1` para regenerarlos a propósito.
- Oficio de la Voz (Spec-470): `voice_craft.md` (narración oral con oraciones completas y conectores, registro de anécdota sin metáforas y con una comparación por acto como mucho (Spec-640), ritmo por largo de párrafo según la intensidad, sugerir antes que nombrar el miedo, cierre concreto, primera persona, léxico; ejemplo antes/después; Spec-590) vía `{guia_oficio}`, y el bloque «CÓMO LLAMÁS A CADA PERSONAJE» (`{parentescos}`). La lista de clichés prohibidos vive en `voice_cliches.txt` (una por línea; la usan el prompt y las métricas). `PromptBuilder` quedó como piezas compartidas: `get_beat_info`, `narrator_name`, `_voice_extras`.

**Evaluar:**
- La prosa: `uv run python scripts/evaluate_voice.py --label <nombre> --runs 2 --out <dir> [--input <yaml>] [--mock]` genera «El monte prohibido» (o la historia de `--input`, con su escaleta, p. ej. `input_stories/no_te_detengas_en_el_bosque.yaml` de la Spec-590) con el perfil activo en una DB temporal y mide clichés, parentescos candidatos, nombre del narrador fuera de diálogo, 4-gramas repetidos, oraciones cortadas, diálogo y palabras por acto (`scripts/voice_metrics.py`). Evidencia en `scripts/research/590/`.
- El asistente: `uv run python scripts/evaluate_workshop.py --runs 2 --out <dir> [--stories pena] [--variants …] [--mock]` compara el camino base con el del asistente (S6; evidencia en `scripts/research/530/`).

## Web & Streaming (Spec-210)

- **Frontend:** Express + EJS + HTMX en `frontend/`. Único origen para el browser. Proxy interno `/api/*` → `CORE_API_URL`.
- **Tema (Spec-531 / Spec-540):** tema claro «Papel» (prod); en dev (`ENV=dev` → `<html data-env="dev">`, `utils/environment.ts`) el tema «Latte» (Catppuccin Latte, bloque `:root[data-env="dev"]` de `theme.css`), `[DEV]` en el título, `favicon-dev.svg` y «DEV · rama · commit» en la barra lateral (leídos de `.git/` en cada request; `GIT_DIR` en el contenedor). Sin `ENV=dev` todo se ve como prod (también los E2E; `E2E_ENV=dev` para capturas de Latte). **Gramática visual (Spec-550 H9):** *botón* hace algo (`.btn-forge*`, redondeado, siempre con el acento; `.btn-forge-outline-danger-sm` para borrar); *chip* dice un estado (`.chip-forge` + `--cumple|--parcial|--falta|--info`, píldora sin borde, nunca `<button>`); *nota* explica o avisa (`.nota-forge--info|warning|error`, barra lateral, acciones como `.nota-forge__accion`); *pista* es la ayuda gris de un campo (`.pista-forge`); *opción* se elige (`.opcion-forge`, elegida = acento lleno y todo el texto en `on-accent`; la compacta es **píldora con borde y marca**, para no confundirse con el botón rectangular ni con el chip sin borde, Spec-630 B10). Lo verifica `gramatica-visual.view.test.ts`. **Estáticos (Spec-630 B17):** `assetVersion` (`utils/assets.ts`, en cada request) sale de la última modificación de `styles.css` y `public/js/`; viaja en `?v=` y en `<meta name="asset-version">`, y `public/js/version-check.js` hace una carga completa si una navegación con `hx-boost` trae otra versión (si no, el `<head>` viejo seguía vivo). **Menú lateral (H3):** `--sidebar-width` 13rem, colapsable a íconos (`--sidebar-width-collapsed`, `<html data-sidebar="collapsed">`, `localStorage` `forge:sidebar`, `public/js/sidebar.js`); el pie de actividad lee el mismo token. La paleta vive **solo** en `frontend/src/styles/theme.css` (`--forge-*`, importado en `globals.css`) y se usa con las clases `forge-*` de Tailwind, que admiten opacidad (`bg-forge-accent/10`, vía `color-mix`). Estados: `error` / `warning` / `success` / `info`, cada uno con `-bg` y `-border`; además `on-accent` y `overlay`. Nada de colores fijos en vistas, estilos ni JS: lo verifican `no-hardcoded-colors` y `palette-contrast` (AA ≥ 4,5:1, las dos paletas). Tipografía: sans en la interfaz, `.prose-forge` (serif, interlineado 1,7) para la prosa. Favicon: vela (`public/favicon.svg`; PNG con `npx ts-node scripts/build-favicons.ts`). Capturas para comparar: `CAPTURAS=<carpeta> npx playwright test visual-snapshots` → `frontend/capturas/531/<carpeta>/`.
- **Jobs (Spec-460):** generar y regenerar un acto son jobs (`generation_job`). `JobManager` (singleton en `src/presentation/runtime.py`) corre cada job como `asyncio.Task`: cerrar la pestaña no lo detiene, `POST /jobs/{id}/cancel` sí. Un solo job activo por historia (lock + índice único parcial) → 409 con el job existente. Al arrancar, los jobs que quedaron activos pasan a `failed` ("interrumpida por reinicio").
- **Eventos (Spec-460):** `EventBus` en memoria con canales `job:<id>` (detalle, lo usa la sala) y `global` (ciclo de vida `job_*`, lo usa todo el resto). Ids por canal → reconexión con `Last-Event-ID`. Ningún GET arranca trabajo.
- **Cliente:** `public/js/event-bus.js` abre 1 `EventSource` global por pestaña (en `<head>`, sobrevive a hx-boost; se cierra en la sala) y re-emite `forge:*` en el DOM. Consumidores: banda de generación, pie (estado del Core), botones `[data-generation-trigger]` (`generation-guard.js`), galería en vivo y paneles atados a un job. Heartbeat 15s no negociable.
- **Tono del sitio (Spec-580):** quienes crean relatos no conocen el oficio: todo texto visible va en tono coloquial (voseo, frases cortas, hechos concretos, sin teoría). En pantalla los pasos son «Tu idea → Preguntas → Los actos → El relato» (las URLs siguen `direccion|taller|escaleta`) y los actos «Cómo empieza · Se complica · El peor momento · Qué hace después · Cómo termina». `sin-jerga.view.test.ts` falla si vuelve la jerga («escaleta», «taller», «beat», «Core»…) a las vistas o a `public/js` (salvo `/debug`, que se abre desde el pie). La prosa de la Voz no cambia de tono.
- **Asistente de autoría (Spec-530):** «Nuevo relato» → `/nuevo`; la historia se trabaja en `/asistente/{id}/{direccion|taller|escaleta}` (`/generar` redirige ahí; el wizard viejo ya no existe). Toda historia se edita en el asistente, también las importadas (sin dirección, la sinopsis es su «¿de qué trata?»). **Editar abre siempre «Los actos»** (Spec-630 B1: `rutas.editarHref` de `utils/rutas.ts`, en `app.locals`). La ficha de la historia ya no existe (B12): `GET /historia/{id}` redirige a «Los actos» o, con un relato escribiéndose, a la sala.
  - **Sin recargar (Spec-630 B5):** las acciones de «Los actos» y «Preguntas» no recargan la página: `run()` → `refresh()` pide `GET /asistente/{id}/fragmento/(escaleta|taller)` (partials `_acto.ejs`, `_escaleta_contenido.ejs`, `_taller_contenido.ejs`), reemplaza solo lo que cambió (la tarjeta del acto, o todas si cambió un personaje o un lugar) y ancla el scroll y el foco. Solo recarga al terminar un análisis de la IA (con el scroll restaurado después de `load`). La referencia del HTML está en `tests/fixtures/asistente/` (`UPDATE_FIXTURES=1`).
  - Autoguardado real desde `public/js/asistente.js` (cola por formulario, `flushAll`) directo a `/api/v1/authoring/*`.
  - Barra fija arriba de todo (`.asistente-barra`, sticky en `<main>`) en Dirección, Taller y Escaleta: los **pasos** (`_cabecera.ejs`, `.pasos-forge`) y los botones de la IA del paso (Spec-550 H11). El guardado se avisa con una **notificación flotante** (`_guardado.ejs`, `.guardado-forge`): «Guardado» ~2 s, «Guardando…» solo si tarda > 1 s, el error queda hasta resolverse o cerrarse; `data-pendiente` marca un guardado en curso (lo esperan los E2E).
  - Confirmaciones con `ForgeConfirm.ask` (`public/js/confirm-dialog.js` + `partials/confirm_dialog.ejs`, un `<dialog>` con el tema): `data-confirmar` del asistente y todo `hx-confirm` (evento `htmx:confirm`; título y botón en `data-confirmar-titulo` / `data-confirmar-label`). Nada de `confirm`/`alert`/`prompt` nativos (test `no-native-dialogs`).
  - Taller: 9 criterios (`workshop_criteria.yaml`, Spec-580) en el orden de los actos: `meta`, `inquietud`, `en_juego`, `vulnerabilidad`, `transgresion`, `historia_secreta`, `descubrimiento`, `reaccion`, `final`. Llevan `{protagonista}` en `nombre` y `por_que` («Qué quiere José»); `Criterion.for_story()` lo reemplaza, también en los prompts del asistente. `acto` (opcional) llega al Planificador como «(va en el acto N)». Los prompts de sistema del Consultor y del Verificador traen la guía de tono (lo que escriben lo lee quien arma la historia). El «para qué sirve» se ve en preguntas abiertas, «Ya resuelto» y chips.
  - Final (Spec-550 H1): **escribirlo es decidirlo**. `Direction.ending_intentional` se deriva de que haya texto en `ending`; no hay casilla.
  - Avisos de la Escaleta (Spec-550 H10): `ActOutline.warnings` es una lista de `OutlineWarning {text, key, source, dismissed}`. Las reglas usan claves estables (`siembra:…`, `elenco:…`, `sin_hechos`, `sin_cambio`); los de la IA, `ia:` + texto normalizado. «Ignorar» / «Volver a mostrar» (`…/warnings/dismiss|restore` con `{key}`) marcan `dismissed`; revisar de nuevo no los trae (el Verificador recibe los descartados y los filtra); rearmar la escaleta los olvida.
  - Las tarjetas de opción son `.opcion-forge` (el label ya es `relative`: si no, el foco de un `sr-only` desplaza el `<body>`).
  - La IA solo con comandos explícitos (jobs `consult` / `plan_outline` / `verify_outline`): un modal bloquea la página (`inert`) hasta que el job termina; se reengancha a un job activo al recargar.
  - Los personajes se suman en el acto donde aparecen (`POST …/characters` con `act`), no todos al inicio. Las reglas se cargan dentro de un acto (`applies_to_beat`). Spec-630: «Sumarlo a los personajes» lo marca en el acto y **resuelve** el aviso (`…/warnings/resolve`, no queda ignorado); «+ Lugar» suma a `story.scenarios` (`POST …/scenarios`, opción en todos los actos); lugares y personajes se borran con su «×» (`…/scenarios/remove`, `…/characters/remove`; quien narra no), con una confirmación que dice en qué actos se usan (`_state`: `characters[].acts`, `scenarios: [{name, acts}]`).
  - La escaleta es editable; los avisos del Verificador se ven y se descartan por acto; un acto queda «a revisar» si cambió la dirección.
  - Round-trip YAML con `python -m src export-yaml` / `import-yaml`: exporta dirección, taller y escaleta; importa también los YAML viejos (ignora `tono`, `traits`, `rule.type` y las claves viejas del narrador).
- **Galería (Spec-311 + Spec-312):** lista variantes de `generated_narrative` por relato + delete con confirmación HTMX. La tarjeta de una historia con guion trae «Para el video» (`video_narrative_id` en `GET /stories`). **No lanza generaciones** (Spec-630 B14): se escribe desde «Los actos» o desde «El relato», siempre por la sala con `?escribir=1` (`startMode` para borrador o fallido, `regenerateMode` para terminado; `?regenerate=1` sigue andando).
- **«El relato» (`/historia/:id/relatos`, Spec-630 B13/B15/B16):** la barra fija con los cuatro pasos; un panel de acciones arriba de las pestañas («Escribir de nuevo la historia completa» y, de la versión elegida, `partials/relato_acciones.ejs`: Corregir, Armar el guion / Para el video, Descargar .md, Copiar); pestañas «Versión del dd/mm/yyyy hh:mm». El panel de la versión (`relato_panel.ejs`) trae la prosa y «Regenerar» por acto; servido solo (`conAcciones`), su grupo de acciones viaja con `hx-swap-oob`.
- **Del relato al video (Spec-610):** todo sale de las acciones de cada versión del relato.
  - **«Corregir el relato»** (`/historia/:id/relatos/:rid/corregir`, D20): un acto a la vez, con autoguardado (`PUT /generated-narratives/{id}/acts/{n}`), avisos de repetición con «Buscar», regla de duración del episodio (`tiempos.js` = `timing.py`, casos compartidos en `tests/fixtures/video/`) y «Regenerar el acto». Regenerar un acto reemplaza **solo ese acto** de la versión y la Voz sigue desde el final corregido del anterior.
  - **«Armar el guion para el video»**: job `video_script` con el modal genérico `ia-modal.js` (`partials/ia_modal.ejs`); la banda de generación no lo muestra.
  - **«Para el video»** (`/historia/:id/relatos/:rid/video`, D22): resumen (quién lee, duración, tipos) y pestañas Guion / La calabaza / Mapa. Todo se edita con autoguardado (`guardado.js`); el remarcado es por posición y por frase (`marcas.js` = `state.py`, casos compartidos), con «Copiar» en los prompts y «Armar de nuevo» con confirmación. Avisa si el relato cambió (`al_dia` / `cambio_el_texto` / `cambiaron_parrafos`).
  - **Archivos (D19: se arman al descargar):** `calabaza.txt` y dos PDF con WeasyPrint (D24). Las plantillas están en `config/video/pdf/` y las fuentes OFL en `assets/fonts/`; las imágenes traen `pango` y `fonts-dejavu-core`. Si cambiaron los párrafos de un acto, los PDF responden 409.
  - **Config:** `config/video/` (`presentador.yaml` = la calabaza y el `cierre_fijo`; `biblia_visual.yaml` = estilo, mezcla de tipos, transiciones, palabras prohibidas; `lectores.yaml`; `lectura.yaml` = 150 palabras/min, episodio 12–17 min). Tipos al azar con semilla por versión (`type_mix.py`). Colores `--forge-tipo-*` en `theme.css`.
- **Exportar para el TTS (Spec-490):** «Descargar .md» en las acciones de cada variante (`relato_acciones.ejs`, `hx-boost="false"`) baja el relato en el formato que lee `audiogen` (proyecto TTS del usuario): `# título`, `## Acto N`, un párrafo por línea y `[pause=1500]` entre actos. `narrative_script_formatter.py` quita lo que `audiogen` saltearía en silencio (líneas que empiezan con `#`/`-`/`*`/`>`: guion de diálogo → raya, énfasis, citas, separadores); el contrato está en `test_narrative_script_audiogen_contract.py`. «Copiar Relato» copia solo los `[data-copy-part]` (rótulos y prosa, sin botones).
- **Tiempo estimado (Spec-510):** cada job guarda en `params` su `profile` y `estimated_seconds`; el payload y `JobResponse` traen `started_at`, `finished_at` y `elapsed_seconds`. `public/js/eta.js` (`window.ForgeEta`, UMD testeable en Vitest) calcula avance y tiempo restante (mezcla la estimación con el ritmo real; redondeado, nunca negativo: «tardando más de lo habitual»); lo usan el banner y la sala (tick de 15 s; `event-bus.js` marca `received_at` para no depender del reloj del Core). Antes de lanzar, el middleware `loadEstimates` (solo asistente, sala y relatos; timeout 1,5 s) deja «≈ N min» en `res.locals.estimateLabels` → partial `estimate.ejs`, confirmación de la sala y `hx-confirm` de regenerar un acto.

## Environment Variables

```
ENV=dev
API_HOST=0.0.0.0:8040
ANTHROPIC_API_KEY=...                              # solo si perfil usa Anthropic
DATABASE_URL=sqlite+aiosqlite:///data/dev/stories.db
PROMPTS_DIR=./config/prompts_generation
BEATS_DEFINITION_FILE=config/llm_beats_definition.yaml
# LLM_PROFILE=ollama-gemma3-12b                    # opcional: pisa active_profile
```

`frontend/.env` independiente (dev): `PORT=3040`, `CORE_API_URL=http://localhost:8040`.

## Database

SQLite vía `aiosqlite`. `init_db()` en `src/infrastructure/database/connection.py` define el esquema. **Dieciséis tablas:**

- `genre`: id, label, order_index — catálogo sembrado por `init_db()` desde `src/infrastructure/database/seeds/genre_catalog.py` (idempotente)
- `subgenre`: genre_id, id, label, order_index — PK compuesta (`otro` existe en cada género)
- `entity_nature`: id, label, order_index — catálogo de naturalezas de entidad; seed `seeds/entity_natures.py` con **upsert** (el seed manda: una etiqueta editada llega a las bases existentes)
- `genre_entity_nature`: genre_id, nature_id — qué naturalezas admite cada género (`desconocida` en todos); el seed solo agrega pares
- `story`: id, title, protagonista, relator, sinopsis, genero, subgenero, narrator_config (JSON: `storyteller_id`, `storyteller_name`, `voice {person, tense}`), direction (JSON: premisa, efecto, final, final intencional, cómo lo cuenta), status, created_at — FK `genero` → `genre` y FK compuesta `(genero, subgenero)` → `subgenre`; par inválido → 422 (`ensure_valid_genre`). `Story.atmosfera` = «género (subgénero)».
- `character`: id, story_id, name, role, kind (`persona`|`sin_nombre`|`grupo`), relation (qué es para quien narra), order_index
- `rule`: id, story_id, content, applies_to_beat (NULL = global)
- `macro_beat`: id, story_id, number, generated_act, status, stale, system_prompt, user_prompt, created_at — **solo la salida** de cada acto (Spec-570; entidad `ActText`)
- `scenario`: id, story_id, order_index, name, description
- `narrative_journal`: id, story_id, beat_number, last_events, physical_emotional_state, used_motifs (JSON), body_state, narrator_traits (JSON) — las dos últimas de la Spec-590
- `generated_narrative`: id, story_template_id, title, content, status
- `entity`: id, story_id, order_index (0 = principal), name, nature_id, description, manifestations, limits, reveal_level — máx. 3 por historia; se reescribe con los datos de entrada
- `story_workshop`: story_id, level (`direccion`|`escaleta`), criterion, status (`cumple`|`parcial`|`falta`|`intencional`), question, options (JSON), answer, round, asked (JSON) — único por (story_id, level, criterion)
- `act_outline`: la escaleta, entrada de cada acto (separada de `macro_beat`, que es la salida): story_id, number 1–5, goal, events, change_from/to, scenario y on_stage (por nombre), held_back («lo que todavía no se cuenta») y reveal_act, seeds, payoffs, decisions, warnings (JSON de `{text, key, source, dismissed}`, Spec-550 H10), needs_review, bridge («cómo llega acá», Spec-560 A1), draft y synopsis (sinopsis por acto de un YAML viejo, Spec-570 D2)
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

- `video_script` (Spec-610): id, narrative_id (único, FK con borrado en cascada), data (JSON: narra, lector, bloques, momentos, calabaza), parrafos_por_acto (JSON), narrative_hash, seed, created_at, updated_at — un paquete por versión del relato. Por eso `SQLGeneratedNarrativeRepository.save()` hace UPSERT y no `INSERT OR REPLACE`, que borraría el paquete en cascada.

## API Endpoints (FastAPI, prefijo `/api/v1`)

- `story_router` — CRUD `/stories` (`PATCH /stories/{id}` edita también generadas; 409 con job activo; 422 si el par género/subgénero no existe o las entidades son inválidas: más de 3, campo largo o naturaleza de otro género), PATCH `status` y `file-path`. `GET /stories/{id}` trae `storyteller_config` (vista de la ficha) y `authoring`.
- `catalog_router` (Spec-440, Spec-450) — `GET /catalog/genres` (géneros con sus subgéneros y sus `entity_natures`, ordenados).
- `authoring_router` (Spec-530) — `/authoring/options`, `POST /authoring/stories`, `GET /authoring/stories/{id}` (estado de Dirección/Taller/Escaleta), `PUT …/direction`, `PATCH …/workshop/{criterio}` (`answer`|`decide`|`intentional`|`reopen`), `PUT …/outline/{n}`, `POST …/outline/{n}/warnings/dismiss|restore|resolve`, `POST …/characters` (`act` opcional) y `…/characters/remove`, `POST …/scenarios` y `…/scenarios/remove` (Spec-630); 409 (con `X-Job-Id`) si hay un job activo. La IA corre como jobs `consult` | `plan_outline` | `verify_outline` (`POST /stories/{id}/jobs`).
- `beat_router` — `GET /stories/{id}/beats` (texto de cada acto; el `PUT` salió con la Spec-570).
- `video_router` (Spec-610) — `GET /video/lectura`; `GET /generated-narratives/{id}/video-script` (con `estado`, `marcas_perdidas`, estilo, transiciones, lectores, cierre fijo); `PUT …/video-script/{reader|blocks/{n}|moments/{n}|presenter}` (409 con la IA trabajando); `GET …/video-script/{calabaza.txt|guion.pdf|mapa.pdf}`. Corregir un acto: `PUT /generated-narratives/{id}/acts/{n}` (`narrative_router`). Armar: job `video_script` con `narrative_id`.
- `job_router` (Spec-460) — `POST /stories/{id}/jobs` (`full_generation` | `regenerate_voz` {beat, narrative_id} | `consult` | `plan_outline` | `verify_outline` | `video_script` {narrative_id}; 202/409/422), `GET /stories/{id}/jobs/active`, `GET /jobs/{id}`, `GET /jobs/estimates` (Spec-510), `POST /jobs/{id}/cancel`, `GET /jobs/{id}/events` (SSE de detalle).
- `events_router` (Spec-460) — `GET /events` (SSE global: `snapshot` + `job_*` + heartbeat).
- `narrative_router` (Spec-300) — `/story-templates/{id}/narratives`, `/generated-narratives/{id}` (GET/DELETE/text), `/generated-narratives/{id}/export.md` (Spec-490: descarga para el TTS), `/generated-narratives/{id}/repetition` (Spec-530: control de repetición).
- `stream_router` (Spec-210) — `GET /stories/{id}/stream` (SSE de **solo lectura**: se ata al job activo o reproduce los beats), `/full`, `/health`, `/config/active-profile`.

## Specs

Las specs autoritativas están en `specs/`. Lectura obligatoria al abordar una feature: el SessionStart hook lista los archivos disponibles. Nombres clave: `010_marco_sdd.md` (convenciones), `530_asistente_autoria_y_escaleta.md` (asistente, escaleta y pipeline actual; reemplaza al de la 180 y al wizard de la 220/440), `210_arquitectura_web_y_streaming.md` (SSE), `460_jobs_asincronos_y_bus_sse.md` (jobs + bus de eventos), `440_wizard_compacto_generos_anidados.md` (catálogo de géneros), `450_entidad_narrativa.md` (entidades / la amenaza), `490_exportar_relato_para_tts.md` (export .md para `audiogen`), `510_tiempo_estimado_generacion.md` (tiempo estimado de los jobs), `520_deploy_desde_imagen.md` (pase a producción), `531_tema_claro_y_favicon.md` (tema y favicon), `540_entorno_dev_siempre_publicado.md` (dev en contenedores detrás de `storymaker.test`, tema de dev), `550_recorrido_ui_asistente.md` (gramática visual, menú, barra, confirmaciones, taller, avisos ignorados), `560_asistente_procesamiento_y_reglas.md` (puente entre actos, lo que no se cuenta, regenerar sin repetir, receta del efecto; resultados de la medición en §3.1), `570_limpieza_dominio_acto.md` (`macro_beat` solo salida, `ActText`), `620_prompts_fuera_del_codigo.md` (prompts en fragmentos Markdown, mensajes en `core_messages.yaml`, test guardián), `630_ui_y_bugs.md` (segundo recorrido de la UI: editar en «Los actos», sin ficha, sin recargar, lugares y personajes, acciones del relato, estáticos con hx-boost, datos del acto a la IA), `610_guion_para_video.md` (del relato al video: corregir el relato, el paquete con guion de lectura, la calabaza y mapa de producción, PDF; MVP hecho, S5 con los chicos pendiente), `590_prosa_de_la_voz_segun_la_prueba.md` (prosa según la prueba con usuarias: oraciones completas, sin diálogo, más material, cuerpo y rasgos en la memoria; anexo `590_anexo_prueba_usuarias.md`) y `600_rumbo_voz_frontier_y_cierre.md` (la Voz en Claude, el resto local; plan de cierre del proyecto).
