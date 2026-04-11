# Contexto del Sistema Legacy (v0.1 - Pre-Refactor)

Este documento describe el estado inicial del proyecto antes de la migración a la **NarrativeForge API** (FastAPI + Clean Architecture).

## 1. Arquitectura Actual
- **Orquestación:** n8n OSS (self-hosted).
- **Frontend/Wizard:** Node.js + Express + EJS (`story-form/`).
- **Base de Datos:** SQLite (`story-form/stories.db`).
- **Generación:** Flujos JSON en `flujos_n8n/` que llaman a Ollama.
- **Prompts:** Archivos `.md` dispersos en `prompts_generacion/`, `prompts_historias/` y `prompts_saneadores/`.

## 2. Estructura de Carpetas Original
```
/
├── flujos_n8n/             # Workflows de n8n (serán reemplazados por el Pipeline en Python)
├── prompts_generacion/      # Prompts base (serán migrados a config/prompts.yaml)
├── prompts_historias/       # Ejemplos de historias
├── prompts_saneadores/      # Lógica de limpieza legacy (será reemplazada por LLMResponseProcessor)
├── story-form/              # Aplicación Node.js (se mantendrá temporalmente como cliente de la API)
│   ├── public/
│   ├── routes/
│   ├── views/
│   └── stories.db           # DB compartida que será migrada a un esquema robusto
└── scripts_db/              # Scripts SQL manuales
```

## 3. Puntos de Dolor (Motivación del Cambio)
1. **Falta de Control:** n8n dificulta el debugging fino de la prosa y el manejo de estados complejos.
2. **Fragmentación:** La lógica de "saneado" está repartida entre n8n y prompts de corrección.
3. **Escalabilidad:** Difícil de testear unitariamente y de mantener bajo control de versiones.

---
*Este documento es solo para referencia histórica durante la migración.*
