# NarrativeForge

> Sistema de generación granular de relatos de terror atmosférico mediante orquestación multi-agente.

NarrativeForge construye historias cohesivas usando una estrategia **beat-by-beat**: la narrativa se divide en 5 actos estructurales, procesados secuencialmente por un pipeline de cinco roles LLM especializados, para garantizar profundidad literaria y coherencia a largo plazo.

---

## 1. El Manifiesto Narrativo (El Qué)

El sistema no genera texto masivo: construye una experiencia anclada en la **Resonancia Narrativa** (unificación Freytag/Aristóteles, Spec-160).

### Los 5 Pilares de Resonancia
Cada historia se ancla en cinco puntos de inflexión extraídos una sola vez al inicio:

| Pilar | Estadio Freytag | Qué captura |
|---|---|---|
| **Hamartia** | Exposición | La grieta psicológica del narrador — vulnerabilidad preexistente. |
| **Hybris** | Acción Ascendente | La transgresión — la lógica que permite cruzar la frontera. |
| **Anagnórisis** | Clímax | La violación de lo sagrado — el detalle sensorial insoportable. |
| **Peripeteia** | Acción Descendente | La trampa espacial — el entorno como antagonista. |
| **Residual** | Desenlace | La mancha — el daño observable que permanece tras el horror. |

Mapeo 1:1 — Beat N recibe el Pilar N. Sin priorizaciones dinámicas. Definición canónica en `config/llm_narrative_definition.yaml`.

### Estructura de Generación (5 Beats)
La historia fluye a través de 5 macro-beats definidos en `config/llm_beats_definition.yaml`. Un **beat** es la unidad mínima de narración (~300–500 palabras) con su propio contexto, reglas y escenario activo. La consolidación final (los 5 beats unidos) se persiste como una **variante** en la tabla `generated_narrative` (Spec-300/312), permitiendo regenerar la misma historia múltiples veces conservando histórico.

---

## 2. El Equipo de Agentes

Cinco roles colaboran en el pipeline (17 llamadas LLM por historia: 1 + 1 + 5 × 3):

| Rol | Llamadas | Responsabilidad |
|---|---|---|
| **Analyst** | 1 | Extrae los 5 Pilares de Resonancia de la sinopsis. |
| **Resolver** | 1 | Distribuye reglas y escenarios cronológicos a cada beat. |
| **Mapper** | 5 | Mapea el evento de la sinopsis al escenario y pilar correspondiente. |
| **Voz** | 5 | Transforma el `narrative_context` técnico en prosa literaria. |
| **Journal** | 5 | Mantiene la memoria viva entre beats (eventos, misterios, estado emocional). |

Detalles en [docs/estandar_diseno_architectural.md](docs/estandar_diseno_architectural.md).

---

## 3. Puesta en Marcha

### Requisitos
- Python ≥ 3.12 + [`uv`](https://github.com/astral-sh/uv)
- Node.js ≥ 18 + npm
- (Opcional) [Ollama](https://ollama.com) corriendo localmente para usar modelos offline.
- (Opcional) `ANTHROPIC_API_KEY` si se usa el perfil `anthropic-sonnet`.

### Instalación
```bash
make install          # uv sync + npm install (backend + frontend)
cp .env.example .env  # ajustar ANTHROPIC_API_KEY si aplica
make db               # crea data/stories.db (SQLite con esquema Spec-180/300)
```

### Modo Web (recomendado — Spec-210)

Levantar ambos servicios en paralelo:

```bash
make dev-all
```

O en terminales separadas:

```bash
# Terminal 1 — Core API (FastAPI)
make api              # → http://localhost:8010

# Terminal 2 — Frontend (Express + EJS + HTMX)
make ui               # → http://localhost:3000
```

| Componente | URL | Descripción |
|---|---|---|
| Frontend | http://localhost:3000 | Wizard, Streaming Room, Galería de relatos |
| Core API | http://localhost:8010 | REST + SSE |
| API Docs | http://localhost:8010/docs | Swagger UI |
| Health | http://localhost:8010/api/v1/health | Diagnóstico SQLite + LLM activo |

**Flujo típico:**
1. Wizard de 5 pasos (Spec-220) → guarda la historia como YAML y crea fila `story` en estado `draft`.
2. Sala de streaming (Spec-210) → consume `/api/v1/stories/{id}/stream` (SSE) y muestra los beats conforme se generan.
3. Al completar la generación, el evento `done` lleva el `narrative_id` (Spec-312) y la galería pasa a mostrar el relato disponible para lectura, copia o regeneración.

### Modo CLI

Generación end-to-end desde un YAML:

```bash
uv run python -m src generate --input input_stories/el_monte_prohibido.yaml
```

Generación con argumentos sueltos:

```bash
uv run python -m src generate \
  --title "La Casa Vacía" \
  --protagonist "Ana" \
  --relator primera_persona \
  --escenarios "Casa/Pueblo" \
  --sinopsis "..." \
  --atmosfera "tenso, opresivo"
```

Otros comandos:

```bash
uv run python -m src generate --story-id <uuid>            # retoma una historia ya creada en DB
uv run python -m src generate --input ... --hasta voz:3    # detiene en checkpoint (Spec-040)
uv run python -m src generate --input ... --debug          # exporta debug_*.md con prompts y respuestas
uv run python -m src generate --mock --title "..."         # corre con MockLLMAdapter (sin LLM real)
uv run python -m src narrate  --story-id <uuid> --beats 1,2,3
uv run python -m src export   --story-id <uuid> --format md
uv run python -m src export-yaml <story_id>                # round-trip Story → YAML (Spec-302)
```

Tras una corrida exitosa (`generate` o el flujo SSE), se popula automáticamente una variante en `generated_narrative` (Spec-312) consultable desde la galería web.

### Configuración

- **Perfiles LLM:** `config/llm_core_definitions.yaml` — perfiles autocontenidos (provider + 4 roles + filtros). Activar uno con `active_profile:` o con la env `LLM_PROFILE=<nombre>`.
  - Perfiles incluidos: `ollama-llama31`, `ollama-mistral`, `ollama-qwen25-14b`, `ollama-mistral-nemo`, `ollama-qwen3-8b`, `ollama-hybrid-voz-qwen3`, `ollama-gemma3-12b`, `anthropic-sonnet`, `gemini-cli`.
- **Pilares aristotélicos:** `config/llm_narrative_definition.yaml`.
- **Estructura de beats:** `config/llm_beats_definition.yaml`.
- **Prompts:** `config/prompts_generation/*.md` (Spec-170).
- **`.env` raíz:** sólo secretos y rutas (`ANTHROPIC_API_KEY`, `DATABASE_URL`, `OUTPUT_DIR`, `PORT`, `LLM_PROFILE` opcional).
- **`frontend/.env`:** `PORT` y `CORE_API_URL` (proxy hacia el Core API).

---

## 4. Manual de Operaciones (Make)

```bash
make help             # lista todos los targets

# Calidad
make test             # pytest -v --cov=src
make lint             # ruff check + ruff format

# Base de datos
make db               # inicializa data/stories.db (idempotente)
make db-clean         # vacía todos los registros sin tirar el esquema
make clean            # limpia __pycache__, .pytest_cache, .ruff_cache

# Historias (CLI)
make list             # lista todas las historias persistidas
make status ARG=<id>  # muestra estado y artefactos de una historia
make generate ARG=<id># regenera una historia existente
make export   ARG=<id># exporta a Markdown
```

Variables:
- `API_HOST` — host:puerto del Core API (default `0.0.0.0:8010`).

---

## 5. Tests

```bash
make test                                      # toda la suite con cobertura
uv run pytest tests/unit/application -v        # un subdirectorio
uv run pytest tests/unit/core/test_orchestrator.py::TestStoryRunner -v
cd frontend && npm test                        # vitest del frontend
```

---

## 6. Documentación adicional

- [docs/estandar_diseno_architectural.md](docs/estandar_diseno_architectural.md) — estándar arquitectural y diagrama Mermaid.
- [CLAUDE.md](CLAUDE.md) — guía para colaborar con Claude Code en este repo.
- `specs/` — especificaciones SDD numeradas, fuente de verdad de cada feature.

### Specs clave para entender el sistema

| Spec | Tema |
|---|---|
| `010_marco_sdd.md` | Framework SDD, naming y reglas arquitecturales. |
| `060_llm_core_definitions_spec.md` | YAML unificado de configuración LLM + normalizer. |
| `070_llm_profiles_spec.md` | Perfiles pre-configurados (`active_profile` + `LLM_PROFILE`). |
| `120_cli_service_container_spec.md` | `CLIContainer`: inyección de dependencias para la CLI. |
| `160_freytag_resonance_spec.md` | Los 5 Pilares Aristotélicos. |
| `170_prompting_asertivo_spec.md` | Sistema de prompts compact para modelos locales. |
| `180_saneamiento_architectural_narrativo.md` | Pipeline secuencial + `narrative_context` pre-baked. |
| `210_arquitectura_web_y_streaming.md` | Frontend Express + SSE + StreamSessionManager. |
| `220_motor_de_autoria_wizard_y_yaml.md` | Wizard de 5 pasos + bidireccionalidad YAML. |
| `230_ciclo_de_vida_y_gestion_historias.md` | Estados de historia y persistencia de artefactos. |
| `300_refactor_dominio_varios_relatos.md` | `GeneratedNarrative` (variantes por historia). |
| `311_fix_galeria_ver_relato_y_delete.md` | Galería con switcher de variantes + delete. |
| `312_fix_persistencia_generated_narrative.md` | Persistencia automática del relato consolidado. |
