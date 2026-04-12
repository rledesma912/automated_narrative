# Contexto del Sistema Legacy (v0.1 - Pre-Refactor)

Este documento describe el estado inicial del proyecto antes de la migración a la **NarrativeForge API** (FastAPI + Clean Architecture).

## 1. Arquitectura Actual
- **Backend:** Python + FastAPI + SQLite (`src/`)
- **Frontend:** Node.js + Express + EJS (`frontend/`)
- **Generación:** Ollama con prompt-based pipeline (`src/application/services/`)
- **Prompts:** Archivos centralizados en `prompt_generacion/` y `prompts_saneadores/`

## 2. Estructura de Carpetas Original
```
/
├── src/                       # Backend Python (FastAPI)
├── frontend/                  # Frontend Node.js (migrado desde story-form/)
├── prompt_generacion/        # Prompts generación
├── prompts_saneadores/       # Prompts saneado
├── output_stories/           # Relatos generados
├── config/                   # Configuración YAML
├── specs/                    # Documentación técnica
└── docker-compose.yml        # Contenedores
```

## 3. Puntos de Dolor Originales (Pre-Refactor)
1. **Falta de Control:** n8n dificulta el debugging fino de la prosa y el manejo de estados complejos.
2. **Fragmentación:** La lógica de "saneado" estaba repartida entre n8n y prompts de corrección.
3. **Escalabilidad:** Difícil de testear unitariamente y de mantener bajo control de versiones.

---

*Este documento conserva el contexto original para referencia histórica.*
