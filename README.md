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
# crear .env con tus secretos (ANTHROPIC_API_KEY si aplica)
make db               # crea data/dev/stories.db (SQLite con esquema Spec-180/300)
```

### Modo Web (recomendado — Spec-210)

Levantar ambos servicios en paralelo:

```bash
make dev
```

O en terminales separadas:

```bash
# Terminal 1 — Core API (FastAPI)
make api              # → http://localhost:8020

# Terminal 2 — Frontend (Express + EJS + HTMX)
make ui               # → http://localhost:3010
```

| Componente | URL | Descripción |
|---|---|---|
| Frontend | http://localhost:3010 | Wizard, Streaming Room, Galería de relatos |
| Core API | http://localhost:8020 | REST + SSE |
| API Docs | http://localhost:8020/docs | Swagger UI |
| Health | http://localhost:8020/api/v1/health | Diagnóstico SQLite + LLM activo |

> Estos puertos son del entorno de **desarrollo** (Spec-325). Producción corre en Docker
> en `:3000` (frontend) / `:8010` (API), con la DB `data/prod/stories.db`, y se actualiza
> solo con `make deploy` desde `main` (Spec-520; `make deploy-check` valida sin tocar nada).

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
- **`.env` raíz:** sólo secretos y rutas (`ANTHROPIC_API_KEY`, `DATABASE_URL`, `PORT`, `LLM_PROFILE` opcional).
- **`frontend/.env`:** `PORT` y `CORE_API_URL` (proxy hacia el Core API).

---

## 4. Manual de Operaciones (Make)

```bash
make help             # lista todos los targets

# Calidad
make test             # pytest -v --cov=src
make lint             # ruff check + ruff format

# Base de datos
make db               # inicializa data/dev/stories.db (idempotente)
make db-clean         # vacía todos los registros sin tirar el esquema
make clean            # limpia __pycache__, .pytest_cache, .ruff_cache

# Historias (CLI)
make list             # lista todas las historias persistidas
make status ARG=<id>  # muestra estado y artefactos de una historia
make generate ARG=<id># regenera una historia existente
make export   ARG=<id># exporta a Markdown
```

Variables:
- `API_HOST` — host:puerto del Core API (dev: `0.0.0.0:8020`).

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

Las que describen el sistema tal como funciona hoy. El resto de `specs/` (040–150, 302, 320) son saneamientos y fixes puntuales ya cerrados, útiles como historia.

**Marco y configuración LLM**

| Spec | Tema |
|---|---|
| `010_marco_sdd.md` | Framework SDD, naming y reglas arquitecturales. |
| `060_llm_core_definitions_spec.md` | `llm_core_definitions.yaml`: proveedores, filtros de respuesta y normalizer. |
| `070_llm_profiles_spec.md` | Perfiles LLM (`active_profile` + `LLM_PROFILE`). |
| `120_cli_service_container_spec.md` | `CLIContainer`: inyección de dependencias para la CLI. |
| `480_voz_en_anthropic.md` | Proveedor por rol (`RoleRoutingAdapter`), `AnthropicAdapter` al día y perfil híbrido con la Voz en Claude (no activo). |

**Pipeline narrativo**

| Spec | Tema |
|---|---|
| `160_freytag_resonance_spec.md` | Los 5 pilares de resonancia (Hamartia → Residual), uno por acto. |
| `170_prompting_asertivo_spec.md` | Prompts compact/frontier, `NarrativeAuditor` y validación del Analyst. |
| `180_saneamiento_architectural_narrativo.md` | Pipeline de 5 actos (Analyst, Mapper, Voz, Journal) y `narrative_context` pre-armado. |
| `410_resolver_determinista_frontend_relatos.md` | Reparto de escenarios sin LLM + vista de relatos y temas. |
| `420_continuidad_narrativa_journal.md` | Misterios sin resolver del journal al acto siguiente. |
| `450_entidad_narrativa.md` | Entidades (la Amenaza): nivel de revelación y exposición por acto. |
| `470_prompt_voz_horror.md` | Prompt de la Voz con oficio de horror y arnés de evaluación (`evaluate_voice.py`). |

**Datos y dominio**

| Spec | Tema |
|---|---|
| `190_restructuracion_modelo_relacional.md` | Modelo relacional SQLite (`init_db()`, sin migraciones). |
| `222_journal_relacional_spec.md` | Journal por acto persistido en tablas. |
| `230_ciclo_de_vida_y_gestion_historias.md` | Estados de la historia y persistencia de artefactos. |
| `300_dominio_relatos_y_variantes.md` | `GeneratedNarrative`: variantes por historia, galería y consolidación. |

**Web, generación y producción**

| Spec | Tema |
|---|---|
| `210_arquitectura_web_y_streaming.md` | Frontend Express como único origen, proxy `/api/*` y SSE. |
| `220_motor_de_autoria_wizard_y_yaml.md` | Wizard de autoría + round-trip YAML. |
| `315_arquitectura_frontend_y_diseno.md` | Arquitectura del frontend, CSS y diseño. |
| `440_wizard_compacto_generos_anidados.md` | Wizard compacto, catálogo de géneros/subgéneros y narrador dinámico. |
| `430_regeneracion_parcial_por_acto.md` | Regenerar un acto (solo la Voz) sobre una variante. |
| `460_jobs_asincronos_y_bus_sse.md` | Generación como jobs (`JobManager`) + bus de eventos SSE (banda, sala). |
| `490_exportar_relato_para_tts.md` | «Descargar .md» para el TTS (`audiogen`) y «Copiar Relato». |
| `510_tiempo_estimado_generacion.md` | Tiempo estimado: antes de lanzar, restante y cuánto tardó. |
| `325_separacion_dev_prod.md` | Dev (:8020/:3010) y prod (Docker :8010/:3000) en la misma máquina. |
| `520_deploy_desde_imagen.md` | Prod cambia solo con `make deploy` desde `main` (config en la imagen). |
