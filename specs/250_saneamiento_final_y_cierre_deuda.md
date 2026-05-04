# Spec-250: Saneamiento Final de Arquitectura y Cierre de Deuda Técnica

## Estado
PENDIENTE — Diseñado para ser el último paso antes de eliminar `mejoras.md`.

---

## 1. Objetivo
Completar el saneamiento de la arquitectura eliminando los últimos focos de acoplamiento en la CLI, refinando la estructura de servicios de prompts y garantizando la resiliencia del sistema ante fallos externos (LLM y DB).

---

## 2. Contexto y Problemas Pendientes

### A. Acoplamiento en la CLI (Issue #6, #18)
A pesar de la existencia de `CLIContainer`, los comandos en `src/cli/commands.py` todavía instancian directamente clases de infraestructura como `MarkdownStoryParser`, `MarkdownRenderer` y repositorios. Esto rompe la inversión de dependencias y dificulta el testing unitario de la capa de presentación.

### B. "Grasa" en la Fachada `PromptBuilder` (Issue #4)
Aunque se ha delegado la lógica pesada, `PromptBuilder` sigue conteniendo métodos extensos con lógica de formateo de strings (ej. `build_journal_prompt`, `build_story_analyst_prompt`). Esta lógica debería residir en las estrategias o en servicios especializados.

### C. Fragilidad ante Errores (Issue #17, #26)
La cobertura de tests para "caminos tristes" (error paths) es baja. El sistema es vulnerable a:
- Respuestas vacías o JSON malformado del LLM.
- Fallos en la conexión con la base de datos.
- Rechazos de contenido por parte del proveedor de IA.

---

## 3. Slices de Implementación

### Slice A: Consolidación de la CLI (Inversión de Dependencias)
**Archivo:** `src/cli/commands.py`
- Eliminar toda instanciación manual (`Parser()`, `Repository()`, `Renderer()`).
- Utilizar `CLIContainer` para resolver todas las dependencias.
- **Acción:** Refactorizar `generate`, `plan`, `narrate`, `export` y `list_stories` para que reciban sus servicios desde el contenedor.

### Slice B: Limpieza Quirúrgica de `PromptBuilder`
**Archivo:** `src/application/services/prompt_builder.py`
- Crear `JournalPromptBuilder` o mover la lógica de `build_journal_prompt` a una estrategia.
- Mover el formateo de `story_analyst` a un componente dedicado.
- Eliminar los fallbacks de texto hardcodeado en la clase base, asegurando que siempre se usen los templates de `TemplateLoader`.

### Slice C: Resiliencia y Manejo de Errores (Core & Use Cases)
**Archivos:** `src/application/use_cases/`, `src/infrastructure/adapters/`
- **JSON Resiliencia:** Mejorar los parsers en `VozUseCase` y `SynopsisBeatMapper` para manejar JSONs malformados o parciales.
- **Excepciones de Dominio:** Implementar `LLMResponseError` y `DatabaseError` y asegurar su captura y propagación semántica en `DirectorUseCase`.

### Slice D: Quick Wins Finales (Saneamiento de Código)
- **Eliminar Alias:** Borrar `CreateStoryPlanUseCase = DirectorUseCase` en `director_use_case.py`.
- **Enum Consistency:** Asegurar que `MacroBeat.status` use el enum `BeatStatus` en lugar de strings planos en toda la aplicación.
- **Cleanup de Config:** Eliminar referencias a variables de entorno obsoletas o no utilizadas mencionadas en `mejoras.md`.

---

## 4. Estrategia de Testing

### Tests de Regresión (Efecto Secundario Cero)
- Ejecutar `make test` para asegurar que el cambio de instanciación en la CLI no rompe los comandos existentes.

### Tests de Error Paths (NUEVOS)
| Caso de Prueba | Ubicación | Verificación |
|---|---|---|
| LLM retorna string vacío | `tests/unit/application/test_voz_error_paths.py` | El sistema lanza `LLMResponseError`. |
| LLM retorna JSON inválido | `tests/unit/application/test_mapper_error_paths.py` | El parser captura el error y aplica estrategia de fallback. |
| Fallo de DB en persistencia | `tests/unit/application/test_director_error_paths.py` | La transacción se revierte y el error se propaga al reporter. |

---

## 5. Criterios de Aceptación (Checklist)

- [ ] `src/cli/commands.py` no contiene la palabra clave `SQLStoryRepository()` ni `MarkdownStoryParser()`.
- [ ] `PromptBuilder` se reduce a < 300 líneas de código (solo delegación).
- [ ] No existen alias confusos como `CreateStoryPlanUseCase`.
- [ ] Se añaden al menos 5 tests unitarios cubriendo fallos de LLM y DB.
- [ ] Se elimina el archivo `mejoras.md` del repositorio tras validar que todos los puntos críticos han sido resueltos.
- [ ] `make lint` y `make test` pasan sin errores.

---
*Este Spec cierra el capítulo de saneamiento de deuda técnica de NarrativeForge.*
