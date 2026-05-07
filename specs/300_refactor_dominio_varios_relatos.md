# Spec300: Evolución del Dominio de Generación de Relatos y Gestión de Datos

## 1. Resumen Ejecutivo

Este documento especifica los cambios necesarios para evolucionar la aplicación NarrativeForge. El objetivo principal es permitir la generación de **múltiples relatos distintos (variantes)** a partir de una única historia plantilla, refinando el dominio de datos, actualizando la interfaz de usuario para gestionar estos relatos, y mejorando las prácticas de gestión de datos y monitorización.

## 2. Objetivos Específicos

1.  **Dominio de Datos y Cardinalidad:** Establecer una relación clara de **uno-a-muchos** entre una "Historia Plantilla" (la definición inicial) y los "Relatos Generados" (las variantes narrativas producidas).
2.  **Experiencia de Usuario Mejorada:**
    *   Eliminar la exportación a Markdown, ya obsoleta.
    *   Implementar la visualización de una lista de relatos generados asociados a una historia.
    *   Proporcionar una función intuitiva de "copiar texto" para cada relato generado.
3.  **Gestión Segura de Datos:**
    *   Modificar el script `db-clean.sh` para que acepte un ID de historia como parámetro, permitiendo la eliminación selectiva de datos.
    *   Asegurar que no existan funciones de backend que eliminen datos de forma masiva o no parametrizada.
4.  **Mejora de la Interfaz de Monitorización:** Optimizar la vista "Sala de Generación — Monitor" para una mejor experiencia de usuario, incluyendo limpieza de componentes, validación de estado y retroalimentación visual (spinner y mensajes) durante la generación.

## 3. Contexto Actual y Problemas Identificados

*   **Generación Actual:** El sistema genera una única narrativa a través de una secuencia de "beats" orquestada por `DirectorUseCase` y `VozUseCase`.
*   **Persistencia:** `Story` (actúa como plantilla), `MacroBeat` (beats individuales), `Rule`, `Scenario`, `NarrativeJournal`, `NarrativeAnchors` son persistidos vía `SQLStoryRepository` y `SQLBeatRepository`.
*   **Exportación a Markdown:** Existe una funcionalidad de exportación a Markdown en `export_router.py` (backend) y `exportStoryHandler` (frontend), la cual se desea eliminar.
*   **Error `FOREIGN KEY constraint failed`:** Al intentar exportar Markdown, el frontend recibe un error 500 del backend, cuyo origen subyacente es una violación de restricción de clave externa en la base de datos. Los logs actuales no detallan la operación exacta que causa el fallo, pero `SQLBeatRepository.save()` y `SQLStoryRepository.save()` son puntos de escritura sospechosos.

## 4. Estrategia de Resolución Arquitectónica

Adoptaremos un enfoque basado en la **Clean Architecture**, separando las responsabilidades en capas bien definidas:

*   **Domain Layer:** Contendrá las entidades de negocio (`StoryTemplate`, `GeneratedNarrative`, `Beat`, `Rule`, `Scenario`), la lógica de negocio central y las interfaces de repositorio.
*   **Application Layer:** Orquestará los casos de uso (use cases) para la gestión de historias, generación de relatos, copiado de texto, eliminación parametrizada y monitorización. Dependerá de las interfaces del Domain Layer.
*   **Infrastructure Layer:** Implementará los detalles de bajo nivel, como el acceso a la base de datos (`aiosqlite` para `stories.db` a través de repositorios concretos), la lógica de scripts (`db-clean.sh`), y la comunicación con otros servicios. Dependerá de las interfaces del Domain Layer.
*   **Presentation Layer:** Incluirá la API del backend (controladores y rutas) y el frontend (vistas y componentes UI). Dependerá de la Application Layer.

Se aplicarán rigurosamente los principios **SOLID, DRY, KISS, OOP, y IDP** para asegurar un diseño robusto y mantenible.

## 5. Diseño del Modelo de Datos para `GeneratedNarrative`

*   **Entidad de Dominio (`src/domain/models.py`):**
    *   Nueva clase `GeneratedNarrative(BaseModel)` con campos:
        *   `id: UUID4` (clave primaria)
        *   `story_template_id: UUID4` (FK a `story.id`)
        *   `title: str`
        *   `content: str`
        *   `status: StoryStatus` (ej. `COMPLETED`, `FAILED`)
        *   `created_at: datetime`
*   **Tabla de Base de Datos (`src/infrastructure/database/connection.py`):**
    *   `CREATE TABLE IF NOT EXISTS generated_narrative (...)`
    *   Columnas: `id` (TEXT PK), `story_template_id` (TEXT NOT NULL), `title` (TEXT NOT NULL), `content` (TEXT NOT NULL), `status` (TEXT DEFAULT 'completed'), `created_at` (DATETIME DEFAULT CURRENT_TIMESTAMP).
    *   `FOREIGN KEY (story_template_id) REFERENCES story(id) ON DELETE CASCADE`.

## 6. Checklist Detallado de Tareas de Implementación

**Fase 1: Modelado y Persistencia de `GeneratedNarrative`**
    1.  **Actualizar `src/domain/models.py`:** Añadir `GeneratedNarrative`.
    2.  **Actualizar `src/infrastructure/database/connection.py`:** Añadir sentencia `CREATE TABLE` para `generated_narrative`.
    3.  **Crear `src/infrastructure/database/repositories/generated_narrative_repository.py`:** Implementar `SQLGeneratedNarrativeRepository` con métodos `save`, `get_by_id`, `get_by_story_template_id`, `delete`, `delete_by_story_template_id`.
    4.  **Adaptar `SQLStoryRepository`:**
        *   Conceptualizar `Story` como `StoryTemplate`.
        *   Modificar `delete(story_id)` para incluir `DELETE FROM generated_narrative WHERE story_template_id = ?` y añadir manejo de errores/logging.

**Fase 2: Orquestación de Generación de Múltiples Relatos**
    5.  **Crear `src/application/use_cases/generate_narratives_use_case.py`:**
        *   Implementar `GenerateNarrativesUseCase` con el método `generate_multiple()`.
        *   Este use case orquestará llamadas repetidas a `DirectorUseCase.execute_full()`.
        *   Consolidará los beats generados para formar `GeneratedNarrative`s y los guardará.
        *   Gestionará el estado de `StoryTemplate`.
    6.  **Adaptar `DirectorUseCase`:**
        *   Evaluar si `execute_full()` necesita modificaciones para ser llamado repetidamente o si su estructura de yield es suficiente para recopilar beats de un relato completo.
    7.  **Adaptar `VozUseCase` y `LLMProvider`:** Asegurar que manejan la generación de contenido para múltiples beats de forma secuencial.

**Fase 3: Modificaciones de API y Frontend**
    8.  **Crear Nuevos Endpoints de API (`presentation/routers/`):**
        *   `POST /story-templates/{template_id}/generate-narratives`
        *   `GET /story-templates/{template_id}/narratives`
        *   `GET /generated-narratives/{narrative_id}/text`
    9.  **Eliminar Funcionalidad de Exportación MD:**
        *   Eliminar `presentation/routers/export_router.py`, `src/application/services/export_service.py`.
        *   Modificar/eliminar `historia.controller.ts`, `deleteMarkdownHandler`, `markdownCheckHandler`, `verMarkdownHandler`, `downloadMarkdownHandler`.
    10. **Refactorizar Frontend (`frontend/src/`):**
        *   Modificar `core_api.service.ts` y controladores para usar nuevos endpoints.
        *   Reemplazar lógica de exportación/vista MD por lista de `GeneratedNarrative`s y botón "Copiar Texto".
        *   Adaptar `streamingRoomPage` y `generate.controller.ts` para el monitor de progreso de múltiples relatos.

**Fase 4: Limpieza y Seguridad de Datos**
    11. **Modificar `scripts/bash/db-clean.sh`:**
        *   Añadir soporte para parámetro `story_template_id` para eliminaciones selectivas.
    12. **Refactorizar Lógica de Eliminación en Backend:**
        *   Actualizar `SQLStoryRepository.delete` y `clear_story_artifacts` para incluir explícitamente la eliminación de `GeneratedNarrative`s asociadas.
        *   Identificar y eliminar/modificar otras funciones de eliminación masiva.

## 7. Estrategia de Pruebas

*   **Pruebas Unitarias:** Para modelos de dominio (`GeneratedNarrative`), use cases (`GenerateNarrativesUseCase`), repositorios (`SQLGeneratedNarrativeRepository`, `SQLStoryRepository`), servicios.
*   **Pruebas de Integración:** API endpoints para generación, listado y obtención de texto de narrativas; pruebas del script `db-clean.sh`.
*   **Pruebas End-to-End (E2E):** Flujo completo de creación de plantilla, generación de múltiples relatos, visualización y copia, eliminación de plantilla y sus relatos. Probar el monitor de generación con múltiples relatos.
*   **Pruebas de Integridad de Base de Datos:** Verificar la correcta implementación de la FK `ON DELETE CASCADE` y la eliminación de `GeneratedNarrative`s junto con sus plantillas.

## 8. Estado del Error `FOREIGN KEY constraint failed`

Este problema sigue sin ser diagnosticado completamente debido a la falta de logs detallados. Las operaciones de escritura en `SQLStoryRepository.save()` (borrado/re-inserción de reglas/escenarios) y `SQLBeatRepository.save()` (asociación de reglas), así como la lectura de datos que podrían estar en un estado inconsistente, son los puntos más probables de fallo. Se recomienda depuración adicional si el error persiste tras la implementación de Spec300, posiblemente con logging mejorado en el backend o inspección directa de la BD si se habilita.

---