# NarrativeForge

> Sistema de generación granular de relatos de terror con IA (Ollama, Anthropic, Gemini).

NarrativeForge construye relatos de terror cohesivos y atmosféricos usando una estrategia **beat-by-beat**: la historia se divide en 5 actos estructurales, cada uno narrado secuencialmente por un conjunto de agentes LLM especializados. El sistema sigue **Spec-Driven Development (SDD)** y **Clean Architecture**.

---

## Conceptos fundamentales

### ¿Qué es un Beat?

Un **beat** es la unidad mínima de narración (~300-500 palabras). La historia no se genera de un golpe; se construye beat a beat siguiendo una escaleta de **5 actos** definida en `config/llm_beats_definition.yaml`. Ese YAML es la única fuente de verdad para la estructura narrativa — nunca se hardcodea el número de beats.

### Los tres agentes LLM

| Agente | Clase | Rol |
|--------|-------|-----|
| **Director** | `DirectorUseCase` | Orquestador punta a punta: corre el mapper y delega la narración beat-by-beat |
| **Voz** | `VozUseCase` | Expande el summary de cada beat en prosa literaria |
| **Journalist** | `MemoryJournalist` | Rastrea eventos, misterios y estado emocional para mantener coherencia cross-beat |

---

## Flujo de generación

### Diagrama de secuencia

```mermaid
sequenceDiagram
    participant CLI
    participant Runner as StoryRunner
    participant Dir as DirectorUseCase
    participant Map as SynopsisBeatMapper
    participant Voz as VozUseCase
    participant Jrn as MemoryJournalist
    participant LLM as LLMProvider
    participant DB as SQLite

    CLI->>Runner: generate(input.md)
    Runner->>DB: CreateStory → story_id

    Runner->>Dir: execute_full(story)

    Dir->>Map: map(story)
    Map->>LLM: generate(role="director")
    LLM-->>Map: N líneas numeradas
    Map-->>Dir: list[Beat] con summaries

    Dir-->>Runner: on_plan_ready(n, elapsed)
    Runner->>DB: save beats (status=pending)

    loop Por cada beat (1..N)
        Dir->>Voz: execute(story, beat, journal)
        Voz->>LLM: generate(role="voz")
        LLM-->>Voz: prosa literaria
        Voz->>Jrn: update_journal(prosa)
        Jrn->>LLM: generate(role="journal")
        LLM-->>Jrn: estado actualizado
        Voz-->>Dir: (beat_completado, journal, elapsed)
        Dir-->>Runner: yield (beat, journal, elapsed)
        Runner->>DB: save beat content + journal
    end

    Runner->>CLI: relato completo (.md)
```

### Diagrama de colaboración entre clases

```mermaid
flowchart TD
    CLI --> Runner["StoryRunner\n(core/orchestrator.py)"]
    Runner --> Dir["DirectorUseCase\n(application/use_cases)"]

    Dir --> Map["SynopsisBeatMapper\n(application/use_cases)"]
    Dir --> Voz["VozUseCase\n(application/use_cases)"]
    Dir --> Jrn["MemoryJournalist\n(application/services)"]

    Map --> PB["PromptBuilder\n(application/services)"]
    Voz --> PB
    Jrn --> PB

    Map --> LLM["LLMProvider\n(domain/interfaces)"]
    Voz --> LLM
    Jrn --> LLM

    Map --> Norm["ResponseNormalizer\n(infrastructure/normalizers)"]
    Voz --> Norm
    Jrn --> Norm

    Map --> DC["DebugCollector\n(application/services)"]
    Voz --> DC
    Jrn --> DC

    PB --> YAML["llm_beats_definition.yaml\n(config)"]
    PB --> Tmpl["Prompt templates\n(config/prompts_generation/)"]

    LLM --> Ollama["OllamaAdapter"]
    LLM --> Anthropic["AnthropicAdapter"]
    LLM --> Gemini["GeminiCLIAdapter"]

    Runner --> BeatRepo["BeatRepository\n(infrastructure/database)"]
    Runner --> StoryRepo["StoryRepository\n(infrastructure/database)"]
```

---

## Arquitectura de prompts

El sistema diferencia la complejidad del prompt según el modelo activo:

```mermaid
flowchart LR
    P[Perfil activo] -->|ollama-*| C[Variante compact]
    P -->|anthropic-* / gemini-*| F[Variante frontier]

    C --> C1[voice_compact.md]
    C --> C2[synopsis_mapper_compact.md]

    F --> F1[voice.md]
    F --> F2[synopsis_mapper.md]
```

| Variante | Modelos | Característica |
|----------|---------|----------------|
| **compact** | Ollama local (Mistral, Llama, Natsumura) | Prompts cortos, directivos, sin secciones anidadas |
| **frontier** | Anthropic, Gemini | Prompts ricos con contexto completo y restricciones dramáticas |

Los templates viven en `config/prompts_generation/`. La variante activa se determina con el campo `prompt_variant` del perfil en `config/llm_core_definitions.yaml`.

---

## Configuración LLM

Toda la configuración LLM vive en **`config/llm_core_definitions.yaml`**. El `.env` se reserva para secretos (`ANTHROPIC_API_KEY`) y paths del sistema.

### Perfiles disponibles

| Perfil | Provider | Uso recomendado |
|--------|----------|-----------------|
| `ollama-natsumura` | Ollama local | Modelo fine-tuneado para narrativa de terror |
| `ollama-llama31` | Ollama local | Más rápido, calidad aceptable |
| `ollama-mistral` | Ollama local | Balance velocidad/calidad |
| `anthropic-sonnet` | Anthropic API | Máxima calidad narrativa |
| `gemini-pro` | Gemini CLI | Alta calidad, sin costo de API |
| `gemini-mixto` | Gemini CLI | Pro para narrativa, Flash para journal |

Activar un perfil: `active_profile: <nombre>` en el YAML o `LLM_PROFILE=<nombre>` como variable de entorno.

### Roles por perfil

Cada perfil define tres roles con sus parámetros LLM propios:

| Rol | Temperatura típica | Propósito |
|-----|--------------------|-----------|
| `director` | 0.3 | Planificación extractiva — fidelidad a la sinopsis |
| `voz` | 0.7 | Narración literaria — creatividad controlada |
| `journal` | 0.2 | Extracción de hechos — máxima precisión |

---

## Modelo de datos (ERD)

```mermaid
erDiagram
    STORY ||--o{ BEAT : contiene
    STORY ||--|| NARRATIVE_JOURNAL : mantiene_estado

    STORY {
        uuid id PK
        string title
        string protagonista
        string relator
        string escenarios
        text sinopsis
        string atmosfera
        text reglas
        string status
        datetime created_at
    }

    BEAT {
        uuid id PK
        uuid story_id FK
        int number
        string summary
        text content
        string status
    }

    NARRATIVE_JOURNAL {
        uuid story_id FK
        text last_events
        text unresolved_mysteries
        text physical_emotional_state
    }
```

---

## Inicio rápido

### Requisitos

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Ollama (para ejecución local)

### Instalación

```bash
uv sync
cp .env.sample .env
bash scripts/bash/init_db.sh
```

### Generar una historia

```bash
# Desde archivo de input (recomendado)
python -m src generate --input input_stories/mi_historia.md

# Con diagnóstico completo de prompts y respuestas LLM
python -m src generate --input input_stories/mi_historia.md --debug
```

### Otros comandos

```bash
python -m src plan <story_id>      # solo fase de planificación
python -m src narrate <story_id>   # solo fase de narración (sobre plan existente)
python -m src export <story_id>    # exportar relato a Markdown
```

### Comandos de desarrollo

```bash
uv run pytest tests/unit/ -v       # tests unitarios
ruff check . && ruff format .      # lint + formato
```

---

## Especificaciones activas

Los siguientes specs definen la arquitectura y el comportamiento actual del sistema:

| Spec | Qué define |
|------|------------|
| [001 — Marco SDD](specs/001_marco_sdd.md) | Convenciones, naming, layering, principios de ingeniería |
| [019 — Progress Reporter](specs/019_progress_reporter_cli.md) | Contrato de `ProgressReporter` y salida de terminal |
| [020 — Anthropic Provider](specs/020_anthropic_provider.md) | Config del adapter Anthropic y env vars |
| [026 — LLM Core Definitions](specs/026_llm_core_definitions_spec.md) | YAML como fuente de verdad única para config LLM |
| [027 — LLM Profiles](specs/027_llm_profiles_spec.md) | Perfiles pre-configurados y precedencia de resolución |
| [029 — Prompt Variants](specs/029_prompt_variants_spec.md) | Sistema compact/frontier de templates |
| [030 — SynopsisBeatMapper](specs/030_synopsis_beat_mapper_spec.md) | Mapeo extractivo de sinopsis a beats estructurales |
| [031 — Prompts Compact](specs/031_prompts_relato_compact.md) | Decisiones de diseño de los templates de relato |
| [034 — Beat #1 sin contexto vacío](specs/034_suprimir_secciones_vacias_beat1.md) | Por qué Beat #1 no recibe secciones de contexto anterior |
| [035 — Director Orquestador](specs/035_director_orquestador_punta_a_punta.md) | Contrato de `execute_full()` / `execute_narration()` |
| [036 — Beat Spec solo en VOZ](specs/036_beat_spec_solo_en_voz.md) | Por qué el mapper no recibe constraints dramáticas |

---

## Licencia

MIT
