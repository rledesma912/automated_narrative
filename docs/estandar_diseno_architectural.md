# Estándar de Diseño Arquitectural (EDA)

> **Enfoque:** Spec-Driven Development (SDD) — La especificación es la fuente de verdad.

## 1. Metodología de Desarrollo (SDD)
NarrativeForge opera bajo el ciclo obligatorio: **Spec → Plan → Task → Implementation**.
- **Trazabilidad:** Cada cambio en el código debe rastrear a un Hito y una Task definida en un Spec en `specs/`.
- **Validación Humana:** No se cierra un hito sin ejecución de tests y checklist de calidad.
- **Documentación de Decisiones:** Las decisiones arquitecturales se registran en Specs antes de codificar.

### Niveles de Rigor SDD
| Nivel | Rol de la Spec | Rol del Código | Cuándo Usar |
|-------|----------------|----------------|-------------|
| **Spec-First** | Guía y restringe output de IA | Entregable primario | Desarrollo de nuevas features |
| **Spec-Anchored** | Gobierna con checkpoints | Entregable validado | Refactorización o deuda técnica |

### Ciclo de Vida del Hito
Cada cambio se organiza en **Hitos** que agrupan **Tasks** atómicas.
- **Qué:** Resultado esperado.
- **Cómo:** Enfoque arquitectónico (Obligatorio antes de codificar).

## 2. Arquitectura del Sistema (Clean Architecture)
El código se organiza en capas concéntricas donde las dependencias solo fluyen hacia adentro:

1. **Domain:** Entidades (`Story`, `MacroBeat`, `NarrativeAnchors`), interfaces y excepciones.
2. **Application:** Casos de uso (`CreateStoryUseCase`, `VozUseCase`, `GenerateNarrativesUseCase`) y servicios (`PromptBuilder`, `NarrativeAuditor`, `MemoryJournalist`).
3. **Infrastructure:** Adapters LLM, loaders YAML, repositorios SQLite, normalizadores y exporters.
4. **Presentation/CLI:** Entrada de usuario vía CLI y API FastAPI.

### Inyección de Dependencias (Spec-250)
La CLI usa `CLIContainer` para resolver dependencias de infraestructura (`LLMProvider`, repositorios, loaders, exporters, `PromptBuilder`, reporter y debug collector). Esto elimina instanciación directa en comandos y permite tests unitarios con doubles.

### Diagrama de Colaboración entre Clases (capas Clean Architecture)
```mermaid
flowchart TD
    subgraph Presentation
        CLI["CLI\nsrc/__main__.py"]
        Commands["commands.py"]
        FastAPI["FastAPI\nstory/beat/narrative/stream routers"]
    end

    subgraph Application
        CreateStory["CreateStoryUseCase"]
        GenerateNarratives["GenerateNarrativesUseCase"]
        Analyst["StoryAnalystService"]
        Resolver["RuleScenarioResolverService"]
        Map["SynopsisBeatMapper"]
        Prompt["PromptBuilder"]
        Voz["VozUseCase"]
        Jrn["MemoryJournalist"]
        Auditor["NarrativeAuditor"]
    end

    subgraph Infrastructure
        Container["CLIContainer"]
        Loader["YamlStoryLoader\ninfrastructure/loaders"]
        Exporter["YamlStoryExporter"]
        Normalizer["ResponseNormalizer"]
        Ollama["OllamaAdapter"]
        MockLLM["MockLLMAdapter"]
        BeatRepo["SQLBeatRepository"]
        StoryRepo["SQLStoryRepository"]
        GenNarrRepo["SQLGeneratedNarrativeRepository"]
    end

    subgraph Domain
        Story["Story\ndomain/models"]
        Beat["MacroBeat\ndomain/models"]
    end

    CLI --> Commands
    Commands --> Container
    Container --> Loader
    Container --> StoryRepo
    Container --> BeatRepo
    Container --> GenNarrRepo
    Container --> Prompt
    Container --> Ollama
    Container --> MockLLM
    Commands --> CreateStory
    FastAPI --> CreateStory
    FastAPI --> GenerateNarratives
    CreateStory --> Story
    CreateStory --> StoryRepo
    GenerateNarratives --> Analyst
    GenerateNarratives --> Resolver
    GenerateNarratives --> Map
    GenerateNarratives --> Prompt
    GenerateNarratives --> Voz
    Analyst --> Normalizer
    Resolver --> Normalizer
    Map --> Normalizer
    Voz --> Normalizer
    Voz --> Auditor
    Voz --> Jrn
    Jrn --> StoryRepo
    Loader --> Story
    Exporter --> StoryRepo
    StoryRepo --> Beat
    BeatRepo --> Story
    GenNarrRepo --> Story
    Ollama --> Normalizer
    MockLLM --> Normalizer
```

## 3. Pipeline de Inteligencia y Secuencia LLM
- **Fuente de Verdad:** `config/llm_core_definitions.yaml` gobierna perfiles, modelos y parámetros por rol.
- **Variantes de Prompting:** `compact` usa prompts directivos para modelos locales; `frontier` admite prompts más ricos para modelos de mayor rendimiento.
- **Prompting Asertivo (Spec-170):** `NarrativeAuditor` detecta boilerplate, baja sensorialidad y calcos de la sinopsis, disparando reintentos cuando corresponde.
- **Normalización:** `ResponseNormalizer` limpia tags de razonamiento (`<think>`, `<thought>`, `<reasoning>`) y relleno conversacional sin alterar Markdown válido.

### Diagrama de Secuencia del Pipeline (17 llamadas LLM total)
```mermaid
sequenceDiagram
    participant Runner as StoryRunner
    participant Ana as StoryAnalystService
    participant Res as RuleScenarioResolver
    participant Map as SynopsisBeatMapper
    participant Prompt as PromptBuilder
    participant Voz as VozUseCase
    participant Jrn as MemoryJournalist
    participant LLM as LLMProvider

    Runner->>Runner: run_full()

    note right of Runner: 1. Analyst (1 LLM)
    Runner->>Ana: extract_anchors()
    Ana->>LLM: generate(role=story_analyst)
    LLM-->>Ana: NarrativeAnchors

    note right of Runner: 2. Resolver (1 LLM)
    Runner->>Res: resolve_distribution()
    Res->>LLM: generate(role=director_distribution)
    LLM-->>Res: rules + scenarios

    note right of Runner: Beat 1
    Runner->>Map: map_one(1)
    Map->>LLM: generate(role=mapper, beat=1)
    LLM-->>Map: beat metadata
    Runner->>Prompt: build_narrative_context(1)
    Prompt-->>Runner: narrative_context
    Runner->>Voz: narrate(1)
    Voz->>LLM: generate(role=voz, beat=1)
    LLM-->>Voz: prosa
    Runner->>Jrn: extract(1)
    Jrn->>LLM: generate(role=journal, beat=1)
    LLM-->>Jrn: journal entry

    note right of Runner: Beat 2
    Runner->>Map: map_one(2)
    Map->>LLM: generate(role=mapper, beat=2)
    LLM-->>Map: beat metadata
    Runner->>Prompt: build_narrative_context(2)
    Prompt-->>Runner: narrative_context
    Runner->>Voz: narrate(2)
    Voz->>LLM: generate(role=voz, beat=2)
    LLM-->>Voz: prosa
    Runner->>Jrn: extract(2)
    Jrn->>LLM: generate(role=journal, beat=2)
    LLM-->>Jrn: journal entry

    note right of Runner: Beat 3
    Runner->>Map: map_one(3)
    Map->>LLM: generate(role=mapper, beat=3)
    LLM-->>Map: beat metadata
    Runner->>Prompt: build_narrative_context(3)
    Prompt-->>Runner: narrative_context
    Runner->>Voz: narrate(3)
    Voz->>LLM: generate(role=voz, beat=3)
    LLM-->>Voz: prosa
    Runner->>Jrn: extract(3)
    Jrn->>LLM: generate(role=journal, beat=3)
    LLM-->>Jrn: journal entry

    note right of Runner: Beat 4
    Runner->>Map: map_one(4)
    Map->>LLM: generate(role=mapper, beat=4)
    LLM-->>Map: beat metadata
    Runner->>Prompt: build_narrative_context(4)
    Prompt-->>Runner: narrative_context
    Runner->>Voz: narrate(4)
    Voz->>LLM: generate(role=voz, beat=4)
    LLM-->>Voz: prosa
    Runner->>Jrn: extract(4)
    Jrn->>LLM: generate(role=journal, beat=4)
    LLM-->>Jrn: journal entry

    note right of Runner: Beat 5
    Runner->>Map: map_one(5)
    Map->>LLM: generate(role=mapper, beat=5)
    LLM-->>Map: beat metadata
    Runner->>Prompt: build_narrative_context(5)
    Prompt-->>Runner: narrative_context
    Runner->>Voz: narrate(5)
    Voz->>LLM: generate(role=voz, beat=5)
    LLM-->>Voz: prosa
    Runner->>Jrn: extract(5)
    Jrn->>LLM: generate(role=journal, beat=5)
    LLM-->>Jrn: journal entry

    note right of Runner: Total: 1 + 1 + 15 = 17 LLM calls
```

**Conteo:** 1 (analyst) + 1 (resolver) + 15 (5 beats × 3) = **17 llamadas LLM**

## 4. Modelo de Datos (ERD)

### Entidades y Cardinalidades (verificadas contra DB)
```mermaid
erDiagram
    STORY ||--o{ MACRO_BEAT : contiene
    STORY ||--o{ NARRATIVE_ANCHORS : analizado_en
    STORY ||--o{ NARRATIVE_JOURNAL : mantiene_estado
    STORY ||--o{ SCENARIO : escenarios
    STORY ||--o{ RULE : reglas
    STORY ||--o{ GENERATED_NARRATIVE : variantes
    MACRO_BEAT ||--o{ MACRO_BEAT_RULE : vincula_reglas
    RULE ||--o{ MACRO_BEAT_RULE : aplicada_en

    STORY {
        text id PK
        text title
        text protagonista
        text relator
        text sinopsis
        text atmosfera
        text status
        json storyteller_config
        json personajes
        text file_path
        text created_at
    }

    NARRATIVE_ANCHORS {
        text id PK
        text story_id FK
        text resonance_hamartia
        text resonance_hybris
        text resonance_anagnorisis
        text resonance_peripeteia
        text resonance_residual
        datetime created_at
    }

    NARRATIVE_JOURNAL {
        int id PK
        text story_id FK
        int beat_number
        text last_events
        text unresolved_mysteries
        text physical_emotional_state
        datetime created_at
    }

    MACRO_BEAT {
        int id PK
        text story_id FK
        int number
        text summary
        text content
        text status
        text technical_context
        text active_scenario_id
        text active_scenario_description
        text narrative_context
        text type
        text created_at
    }

    MACRO_BEAT_RULE {
        int macro_beat_id PK, FK
        text rule_id PK, FK
    }

    SCENARIO {
        text id PK
        text story_id FK
        int order_index
        text name
    }

    RULE {
        text id PK
        text story_id FK
        text content
        text type
        text intensity
    }

    GENERATED_NARRATIVE {
        text id PK
        text story_template_id FK
        text title
        text content
        text status
        datetime created_at
    }
```

`macro_beat.active_scenario_id` es una referencia lógica al escenario activo, pero no tiene FK declarada en SQLite. `narrative_anchors` se gestiona como un registro activo por historia desde el repositorio, aunque el esquema actual no declara `UNIQUE(story_id)`.

## 5. Estándares de Calidad
- **Python:** 3.12+, tipado explícito y `pydantic` para validación de entrada y dominio.
- **Naming:** `PascalCase` para clases, `snake_case` para funciones/variables y `MAYUSCULAS_SNAKE` para constantes.
- **Testing:** Cobertura obligatoria > 80% con `pytest-asyncio`; cada task de lógica requiere test unitario.
- **Persistencia:** SQLite asíncrono (`aiosqlite`). YAML inicializa la estructura; la DB gobierna el estado de la historia.
- **Errores:** Jerarquía tipada basada en excepciones de dominio e infraestructura, con mensajes de usuario en español.

## 6. Workflow del Desarrollador
- `make install`: Sincroniza dependencias Python con `uv` y dependencias del frontend.
- `make test`: Ejecuta la suite completa de pruebas.
- `make lint`: Ejecuta `ruff check` y formato.
- `bash scripts/bash/init_db.sh`: Recrea la base de datos desde cero.

---
*Este documento es la fuente de verdad técnica del proyecto.*
