# Proyecto NarrativeForge: Instrucciones y Convenciones

## Mandatos Técnicos del Core
- **Modelos de Dominio:** Todas las entidades (`Story`, `MacroBeat`, `GeneratedNarrative`) y DTOs deben usar `model_config = {"extra": "forbid"}` de Pydantic para evitar campos huérfanos y asegurar la integridad de los datos.
- **Orquestación:** El `StoryRunner` (en `orchestrator.py`) y otros orquestadores de alto nivel deben interactuar preferentemente mediante DTOs (ej: `run_full_from_dto`). Se prohíbe la explosión de parámetros individuales en firmas de métodos de orquestación.
- **Validación Estricta:** Los campos obligatorios de la historia (título, sinopsis, etc.) deben tener validación de longitud mínima (`min_length=1`) para evitar persistir registros vacíos desde flujos CLI o API.
- **Persistencia de Relatos:** La generación de un `GeneratedNarrative` es un efecto colateral obligatorio de finalizar con éxito cualquier pipeline de generación (CLI o Web).
- **No Migration Scripts:** No se utilizan scripts de migración de base de datos. Si el esquema cambia, se debe recrear `stories.db` usando `./scripts/bash/init_db.sh`.

## Estándares de Frontend
- **Arquitectura CSS:** Uso estricto de Tailwind CLI. Prohibido el uso de CDN en producción.
- **Componentización:** Preferir clases semánticas `.btn-forge*` definidas en `globals.css` sobre clases Tailwind inline repetitivas.
- **Renderizado:** Todas las vistas deben pasar por `renderPage()` para mantener la consistencia del layout (sidebar/footer).
