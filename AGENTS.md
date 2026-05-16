# AGENTS.md — NarrativeForge

Guía operativa para agentes (OpenCode y similares) que trabajan en este repositorio.
Las specs en `specs/` son la **fuente de verdad**; este archivo y `CLAUDE.md` son
quickstarts. Idioma de trabajo: **español**.

## Project Context

NarrativeForge genera relatos de terror atmosférico mediante un pipeline secuencial
de 5 macro-beats orquestado por cinco roles LLM especializados (Spec-180).

**Stack:** Python 3.12 · FastAPI · aiosqlite · Clean Architecture · Express + EJS +
HTMX (frontend) · LLM vía Ollama / Anthropic / Gemini CLI / Mock.

**Comunicación web:** SSE (Server-Sent Events), no WebSocket.

## Metodología: SDD (OBLIGATORIO)

Flujo: **SPECIFY → PLAN → TASKS → IMPLEMENT**. No avanzar de fase sin OK explícito
del usuario.

1. Antes de implementar: verificar si existe spec en `specs/`. Si no, crear uno
   siguiendo `.opencode/skills/spec-driven-development/SKILL.md`.
2. Slices incrementales (`.opencode/skills/incremental-implementation/SKILL.md`).
3. DB: **no se generan scripts de migración**. Cambios de esquema → actualizar
   `init_db()` en `src/infrastructure/database/connection.py` y recrear la DB.

### Skills por fase (`.opencode/skills/`)

| Fase | Skill |
|------|-------|
| Define  | `spec-driven-development`, `idea-refine` |
| Plan    | `planning-and-task-breakdown` |
| Build   | `incremental-implementation`, `source-driven-development` |
| Verify  | `debugging-and-error-recovery`, `test-driven-development` |
| Review  | `code-review-and-quality`, `code-simplification` |
| Ship    | `git-workflow-and-versioning`, `shipping-and-launch`, `ci-cd-and-automation` |

## Specs clave

| Spec | Tema |
|------|------|
| `010_marco_sdd.md` | Convenciones SDD, naming, reglas arquitecturales. |
| `060_llm_core_definitions_spec.md` | YAML unificado de configuración LLM + normalizer. |
| `070_llm_profiles_spec.md` | Perfiles pre-configurados (`active_profile` / `LLM_PROFILE`). |
| `120_cli_service_container_spec.md` | `CLIContainer`: inyección de dependencias para la CLI. |
| `160_freytag_resonance_spec.md` | Los 5 Pilares de Resonancia (Freytag/Aristóteles). |
| `170_prompting_asertivo_spec.md` | Sistema de prompts compact para modelos locales. |
| `180_saneamiento_architectural_narrativo.md` | Pipeline secuencial + `narrative_context`. |
| `210_arquitectura_web_y_streaming.md` | Frontend Express + SSE + `StreamSessionManager`. |
| `220_motor_de_autoria_wizard_y_yaml.md` | Wizard de 5 pasos + round-trip YAML. |
| `300_dominio_relatos_y_variantes.md` | `GeneratedNarrative` (variantes por relato). |
| `325_separacion_dev_prod.md` | Segregación de entornos dev/prod en host único. |

El SessionStart hook lista el set completo de specs disponibles.

## Entornos (Spec-325)

| Servicio | Desarrollo (host) | Producción (Docker) |
|----------|-------------------|---------------------|
| Frontend (Express) | `3010` | `3000` |
| Backend (FastAPI)  | `8020` | `8010` |
| SQLite DB          | `data/dev/stories.db` | `data/prod/stories.db` |
| Config de entorno  | `.env` (lee `src/config.py`) | `.env.prod` (vía `docker-compose.yml`) |

> No existe `.env.dev`: `src/config.py` carga `.env` de forma fija. Dev usa `.env`.

## Dev Commands (Make)

```bash
make install     # uv sync + npm install
make api         # uvicorn dev con hot-reload (→ :8020)
make ui          # frontend Express con hot-reload (→ :3010)
make dev         # api + ui en paralelo
make db          # inicializa data/dev/stories.db (idempotente)
make db-clean    # vacía registros de dev sin tirar el esquema
make test        # pytest -v --cov=src
make lint        # ruff check + ruff format
```

**Orden recomendado:** `make lint` → `make test` → review.
**Producción:** `docker compose up -d` (usa `.env.prod`, puertos `3000`/`8010`).

## CLI Commands (`python -m src`)

```bash
uv run python -m src generate --input <yaml> [--mock] [--debug] [--hasta <checkpoint>]
uv run python -m src generate --story-id <uuid>      # retoma una historia ya creada
uv run python -m src plan      --title "..."
uv run python -m src narrate   --story-id <uuid> --beats 1,2,3
uv run python -m src export    --story-id <uuid> --format md
uv run python -m src export-yaml <story_id>          # round-trip Story → YAML (Spec-302)
```

- `--mock`: usa `MockLLMAdapter` (sin LLM real). `--debug`: exporta prompts/respuestas.
- `--hasta` (Spec-040): checkpoints `analyst`, `mapper:1..5`, `voz:1..5`, `journal:1..5`.
- YAML de ejemplo en `input_stories/` (`barco_fantasma.yaml`, `el_monte_prohibido.yaml`).

## Architecture

Clean Architecture: cuatro capas + `core` + `cli`.

```
src/
├── __main__.py       # Entry point CLI: python -m src
├── main.py           # Entry point FastAPI
├── config.py         # Config (pydantic-settings; carga .env + perfil LLM)
├── domain/           # Entities, Interfaces (LLMProvider), DTOs, exceptions
├── application/      # Use Cases + Services (PromptBuilder, StoryAnalyst, ...)
│   ├── use_cases/
│   ├── services/
│   └── dto/
├── infrastructure/   # Adapters LLM + repos SQLite + loaders/exporters YAML
│   ├── adapters/     # Ollama, Anthropic, GeminiCLI, Mock
│   ├── database/     # connection.py (init_db) + repositories/
│   ├── loaders/  exporters/  mappers/  normalizers/  parsers/  renderers/
├── presentation/     # FastAPI routers (story, beat, narrative, stream) + schemas
├── core/             # StoryRunner orchestrator
└── cli/              # CLI runner, commands, logger, progress reporter
```

## Pipeline (Spec-180)

Cinco roles LLM por historia (17 llamadas: 1 + 1 + 5×3):

| Rol | Llamadas | Responsabilidad |
|-----|----------|-----------------|
| Analyst  | 1 | Extrae los 5 `NarrativeAnchors` (pilares Freytag) de la sinopsis. |
| Resolver | 1 | Distribuye reglas y escenarios a cada beat. |
| Mapper   | 5 | Extrae el evento del beat N + escenario activo. |
| Voz      | 5 | Expande el `narrative_context` pre-construido a prosa. |
| Journal  | 5 | Extrae el `memory_snapshot` del beat narrado. |

El VOZ **solo genera prosa**: recibe un `narrative_context` ya ensamblado
determinísticamente (sin LLM) por `PromptBuilder.build_narrative_context()`.

## Important Notes

- **Config:** secretos y paths en `.env`; configuración LLM en
  `config/llm_core_definitions.yaml` (perfiles). Override: `LLM_PROFILE` env.
- **DB:** SQLite vía `aiosqlite`; esquema en `init_db()` (`connection.py`). Ocho tablas.
- **Naming:** PascalCase clases / snake_case funciones (Python); camelCase vars /
  kebab-case archivos (JS); singular snake_case en DB. Detalle en `specs/010_marco_sdd.md`.
- **Linting:** `ruff` (config en `pyproject.toml`).
- **Logs:** `logs/narrative-{YYYYMMDD}.log`.
- **Provider activo:** definido en el perfil del YAML; override con `LLM_PROVIDER` env
  o `--provider` en CLI.
