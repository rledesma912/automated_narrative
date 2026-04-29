# Estándar de Diseño Arquitectural (EDA)

> **Enfoque:** Spec-Driven Development (SDD) — La especificación es la fuente de verdad.

## 1. Metodología de Desarrollo (SDD)
NarrativeForge opera bajo el ciclo obligatorio: **Spec → Plan → Task → Implementation**.

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

### Diagrama de Colaboración entre Clases
```mermaid
flowchart TD
    CLI --> Runner["StoryRunner\n(core/orchestrator.py)"]
    Runner --> Dir["DirectorUseCase\n(application/use_cases)"]

    Dir --> Ana["StoryAnalystService\n(application/services)"]
    Dir --> Res["RuleScenarioResolverService\n(application/services)"]
    Dir --> Map["SynopsisBeatMapper\n(application/use_cases)"]
    Dir --> Voz["VozUseCase\n(application/use_cases)"]
    Dir --> Jrn["MemoryJournalist\n(application/services)"]

    Ana --> LLM["LLMProvider\n(domain/interfaces)"]
    Res --> LLM
    Map --> LLM
    Voz --> LLM
    Jrn --> LLM

    LLM --> Ollama["OllamaAdapter"]
    LLM --> Anthropic["AnthropicAdapter"]
    LLM --> Gemini["GeminiCLIAdapter"]

    Runner --> BeatRepo["BeatRepository\n(infrastructure/database)"]
    Runner --> StoryRepo["StoryRepository\n(infrastructure/database)"]
```

### Capas y Responsabilidades
1. **Domain:** Entidades puras y contratos (`interfaces.py`).
2. **Application:** Casos de uso que orquestan el flujo narrativo.
3. **Infrastructure:** Implementación de adapters, repositorios y normalizadores.
4. **Presentation:** CLI y API (FastAPI).

## 3. Pipeline de Inteligencia y Secuencia LLM

### Diagrama de Secuencia del Pipeline (17 llamadas LLM)
```mermaid
sequenceDiagram
    participant Runner as StoryRunner
    participant Dir as DirectorUseCase
    participant Ana as StoryAnalystService
    participant LLM as LLMProvider

    Runner->>Dir: execute_full(story)
    Dir->>Ana: extract_anchors(story)
    Ana->>LLM: generate(role=story_analyst)
    LLM-->>Ana: NarrativeAnchors (5 pilares)

    loop Por cada beat (1..5)
        Dir->>Dir: build_narrative_context() (Determinístico)
        Dir->>Voz: narrate(nc)
        Voz->>LLM: generate(role=voz)
        LLM-->>Voz: prosa literaria
        Dir->>Jrn: extract()
        Jrn->>LLM: generate(role=journal)
    end
```

## 4. Modelo de Datos (ERD)
```mermaid
erDiagram
    STORY ||--o{ MACRO_BEAT : contiene
    STORY ||--|| NARRATIVE_ANCHORS : analizado_en
    STORY ||--|| NARRATIVE_JOURNAL : mantiene_estado

    STORY {
        text id PK
        text title
        text sinopsis
        text status
    }

    NARRATIVE_ANCHORS {
        text resonance_hamartia
        text resonance_hybris
        text resonance_anagnorisis
        text resonance_peripeteia
        text resonance_residual
    }

    MACRO_BEAT {
        int number
        text summary
        text content
        text narrative_context
        text memory_snapshot
    }
```

## 5. Estándares de Calidad
- **Normalización:** `ResponseNormalizer` elimina ruidos del LLM (ej. tags `<think>`).
- **Auditoría (Spec-170):** El `NarrativeAuditor` valida sensorialidad y boilerplate antes de aceptar una respuesta.
- **Testing:** Cobertura obligatoria > 80% con `pytest-asyncio`.

---
*Este documento es la fuente de verdad técnica del proyecto.*
