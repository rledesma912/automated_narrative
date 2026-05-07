# Fase de Saneamiento del Relato

## Propósito

Sistema crítico-correctivo para mejorar relatos generados (beat-by-beat). **No genera contenido nuevo** — evalúa, corrige y optimiza narrativa existente.

## Pipeline

```
Ingesta →【Auditoría】→【Clasificación】→【Plan】→【Patch】→【Validación】→【Loop】
```

### Fases

| Fase | Actor | Descripción |
|------|-------|-------------|
| 0 | Normalizer | Segmenta por beats/párrafos, limpia artefactos |
| 1 | Auditor | Audit multdimensional → lista de issues |
| 2 | IssueResolver | Prioriza issues, agrupa en PatchSets |
| 3 | PatchPlanner | Propone estrategia (micro_edit, paragraph_rewrite, beat_rewrite, style_overlay) |
| 4 | Rewriter | Aplica patches, preserva eventos y anchors |
| 5 | Validator | Re-auditoría, decide aceptar/retry |
| 6 | Director | Controla iteraciones (max 3), thresholds |

## Modelo de Datos (ERD)

### Entidades del Dominio de Saneamiento

```mermaid
erDiagram
    STORY ||--o{ MACRO_BEAT : contiene
    STORY ||--o{ SANITIZATION_ISSUE : detecta
    STORY ||--o{ SANITIZATION_REPORT : genera
    MACRO_BEAT ||--o{ SANITIZATION_ISSUE : tiene
    SANITIZATION_ISSUE ||--o{ PATCH_SET : requiere
    PATCH_SET ||--o{ PATCH : contiene

    STORY {
        text id PK
        text title
        text protagonista
        text atmosfera
        text status
    }

    MACRO_BEAT {
        int id PK
        text story_id FK
        int number
        text summary
        text content
        text status
    }

    SANITIZATION_ISSUE {
        text id PK
        text story_id FK
        text beat_id FK
        text tipo
        int severidad
        text ubicacion
        text descripcion
        text estrategia_sugerida
        text estado
        datetime created_at
    }

    SANITIZATION_REPORT {
        text id PK
        text story_id FK
        json resumen_auditoria
        int issues_total
        int issues_criticos
        text estado
        datetime created_at
    }

    PATCH_SET {
        text id PK
        text issue_id FK
        text target
        text estrategia
        text estado
        datetime created_at
    }

    PATCH {
        text id PK
        text patch_set_id FK
        text beat_id FK
        text tipo_intervencion
        text original
        text patched
        text diff
        boolean aplicado
    }
```

### Decisiones Clave

| Área | Decisión |
|------|----------|
| Modo | Híbrido (auto + intervención humana en críticos) |
| Granularidad | Mixto (párrafo + beat) |
| Iteraciones | Máximo 3 |
| Dimensiones v1 | Coherencia, Voz, Densidad sensorial |
| Criterio Calidad | Sin issues críticos |

## Riesgos

- Drift narrativo / Sobre-edición / Latencia

## Roadmap

- **MVP:** Auditoría 3 dimensiones + patch párrafo + 1 iteración
- **v1:** Loop completo (3 iteraciones) + granularidad mixta
- **v2:** SSE + UI interactiva

---

## Diagrama de Flujo

```mermaid
flowchart TD
    A["📥 Ingesta y Normalización"] --> B["🔍 Auditoría Multidimensional"]
    B --> C["🎯 Clasificación y Priorización"]
    C --> D["📋 Planificación de Patches"]
    D --> E["✏️ Aplicación de Patches"]
    E --> F["✅ Validación"]
    F --> G{"¿Aceptar?"}
    
    G -->|Sí| H["💾 Persistir"]
    G -->|No| I{"¿Límite iteraciones?"}
    I -->|Sí| H
    I -->|No| B
    
    H --> J["📤 Fin"]
    
    B -.->|Detecta issues| K[("IssueQueue")]
    D -.->|Propone| L{"Usuario\ndecide?"}
    E -.->|Preview| M[("Diff Preview")]
    
    style A fill:#1a1a2e,color:#fff
    style B fill:#16213e,color:#fff
    style C fill:#0f3460,color:#fff
    style D fill:#1a1a2e,color:#fff
    style E fill:#16213e,color:#fff
    style F fill:#0f3460,color:#fff
    style G fill:#e94560,color:#fff
    style H fill:#00d9ff,color:#000
    style J fill:#00d9ff,color:#000
```

## Diagrama de Secuencia

```mermaid
sequenceDiagram
    participant User as Usuario
    participant Director as SanitizationDirector
    participant Normalizer as IngestNormalizer
    participant Auditor as NarrativeAuditor
    participant Resolver as IssueResolver
    participant Planner as PatchPlanner
    participant Rewriter as Rewriter
    participant Validator as Validator
    participant DB as Repositorio
    participant LLM as LLM Provider

    User->>Director: sanitize(story_id)

    loop Max 3 iteraciones
        Director->>Normalizer: normalize(story_id)
        Normalizer->>DB: get_beats(story_id)
        DB-->>Normalizer: beats[]
        Normalizer-->>Director: normalized_story

        Director->>Auditor: audit(multi-dimensional)
        Auditor->>LLM: generate(audit_report)
        LLM-->>Auditor: issues[]
        Auditor-->>Director: audit_report

        alt tiene issues críticos
            Director->>Resolver: classify(issues)
            Resolver-->>Director: prioritized_issues

            Director->>Planner: plan_patches(issues)
            Planner->>LLM: generate(patch_proposals)
            Planner-->>Director: patch_sets[]

            Director->>Rewriter: apply_patches(patch_sets)
            Rewriter->>LLM: generate(patched_content)
            Rewriter->>DB: update_beats(patched)
            DB-->>Rewriter: confirm
            Rewriter-->>Director: patches_applied

            Director->>Validator: validate()
            Validator->>LLM: generate(validation)
            Validator-->>Director: validation_result
        else sin issues críticos
            Director->>Validator: validate()
            Validator-->>Director: validation_result (aceptado)
        end

        alt validación aceptada
            Director-->>User: resultado (éxito)
        else validación rechazada y hay iteraciones
            Director->>Director: siguiente iteración
        else validación rechazada y sin iteraciones
            Director-->>User: resultado (límite alcanzado)
        end
    end
```

## Notas de Diseño