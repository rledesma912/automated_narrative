# Marco SDD - Puntos para Spec

## Puntos del Marco SDD para Spec

| # | Área | Descripción |
|---|-----|-------------|
| 1 | **Objective** | Qué construimos y por qué. User stories o acceptance criteria. |
| 2 | **Commands** | Comandos ejecutables con flags (build, test, lint, dev). |
| 3 | **Project Structure** | Dónde vive el código, tests, docs. |
| 4 | **Code Style** | Un snippet real muestra el estilo. Convenciones de naming. |
| 5 | **Testing Strategy** | Framework, ubicación, coverage expectations. |
| 6 | **Boundaries** | Always do / Ask first / Never do. |
| 7 | **Success Criteria** | Condiciones específicas y testables. |
| 8 | **Open Questions** | Lo que necesita input humano. |
| 9 | **Assumptions** | Lo que asumimos (corregir si está mal). |

---

## Puntos Importantes Adicionales del Spec 009

| # | Punto | Detalle |
|----|------|---------|
| 1 | **Arquitectura de 3 roles LLM** | Director (plan), Voz (prosa), Journalist (coherencia). |
| 2 | **Modelo de datos** | Beat, StoryPlan, NarrativeJournal, Story con campos específicos. |
| 3 | **Flujo con intervención humana** | Usuario puede editar beats antes de narrar. |
| 4 | **WebSocket events** | plan_generated, beat_started, beat_completed, job_completed, job_failed. |
| 5 | **Hitos de implementación** | 6 hitos con tareas específicas. |
| 6 | **Plan de deprecated** | Componentes legacy identificados para eliminación. |
| 7 | **DB tables** | SQL específico para stories, beats, story_plans, narrative_journal. |
| 8 | **Tech stack** | Python 3.12, FastAPI, SQLite, Ollama (qwen2.5:32b, gemma2:9b). |
| 9 | **Criterios de éxito** | 2500+ palabras, VRAM < 4GB, tiempo < 30 seg/beat, coherencia narrativa, UI editable, export Markdown, coverage > 80%. |
| 10 | **Preguntas abiertas** | Qué modelo Ollama usar, cantidad fija de beats, eliminar frontend legacy. |

---

## Assumptions del Proyecto Actual

- **Backend:** Python 3.12 + FastAPI
- **LLM:** Ollama con modelos locales (qwen3.5:9b, gemma4:e4b)
- **DB:** SQLite con aiosqlite
- **Frontend:** Node.js separado en puerto 3010
- **Puerto API:** 8010 (no 8000)

→ Corregir si está mal.