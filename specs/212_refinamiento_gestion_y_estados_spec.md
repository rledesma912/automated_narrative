# Spec-212: Refinamiento de Gestión de Artefactos, Ciclos de Vida y UX de Autoría

## 1. Visión de Arquitectura (Senior Architect Perspective)
Este spec evoluciona el sistema hacia un **Modelo de Autoría Iterativo**. Se aplican principios de diseño robusto para desacoplar la persistencia de la configuración (Historia) de sus artefactos efímeros (Beats, Journal, Markdown).

### Principios Aplicados:
*   **SOLID (Single Responsibility):** Segregación de la lógica de "Hard Delete" (borrado total) de la de "Cleanup" (limpieza para reinicio).
*   **IDD (Interface-Driven Development):** Definición de contratos claros entre el Core y el Frontend para la gestión de estados y paths.
*   **KISS & DRY:** Simplificación de la lógica de UI y reutilización de controladores de exportación para la gestión de borrados.
*   **Transaction Integrity:** El reinicio de historias debe ser una operación atómica en la base de datos.

---

## 2. Slice B1: Backend - Capa de Persistencia y Reinicio Limpio
**Objetivo:** Permitir que una historia vuelva a generarse desde cero sin residuos de ejecuciones previas.

*   **Repository (`src/infrastructure/database/repositories/story_repository.py`):**
    *   Implementar `clear_story_artifacts(story_id: UUID)`:
        *   Eliminar registros en `macro_beat` donde `story_id = story_id`.
        *   Eliminar registro en `narrative_journal` donde `story_id = story_id`.
        *   Opcional: Limpiar `narrative_anchors` si aplica.
        *   *Restricción:* Usar un bloque `async with self.db.begin():` (o equivalente) para asegurar transaccionalidad.
*   **Service (`src/application/services/streaming_service.py`):**
    *   En `stream_story()`, antes de la lógica del productor principal, invocar `repo.clear_story_artifacts()` si el estado es `completed` o `failed`.
    *   Registrar evento en `ObservabilityService`: `"Limpiando artefactos previos para reinicio de narrativa"`.

---

## 3. Slice B2: Backend - API de Desvinculación de Markdown
**Objetivo:** Permitir que la UI informe al Core que un archivo ha sido eliminado.

*   **Router (`src/presentation/routers/story_router.py`):**
    *   Asegurar que el endpoint `PATCH /stories/{id}/file-path` soporte recibir `null` o una cadena vacía para resetear la columna `file_path`.
*   **Observabilidad:** Registrar el cambio de path en el historial de eventos.

---

## 4. Slice F1: Frontend - Gestión de Archivos y Controladores
**Objetivo:** Implementar la lógica de borrado físico del Markdown.

*   **Service (`frontend/src/services/core_api.service.ts`):**
    *   Añadir `updateFilePath(storyId: string, filePath: string | null)`.
*   **Controller (`frontend/src/controllers/historia.controller.ts`):**
    *   Implementar `deleteMarkdownHandler`:
        1. Obtener datos de la historia desde el Core.
        2. Resolver path absoluto del archivo en `public/output_stories/`.
        3. Ejecutar `fs.unlinkSync()` con validación previa de existencia (`fs.existsSync`).
        4. Llamar al Core para poner `file_path` a `null`.
        5. Retornar respuesta JSON exitosa.

---

## 5. Slice F2: Frontend - Refinamiento de UI y Estados
**Objetivo:** Restaurar la visibilidad de estados y habilitar la edición universal.

*   **Vistas (`gallery.ejs`, `historia.ejs`):**
    *   **Estados:** Restaurar `STATUS_LABEL.completed` ("Completada") en color verde (`text-green-500` o similar).
    *   **Edición:** Habilitar el botón "Editar" para historias `completed`. La lógica de visibilidad debe ser `status !== 'processing'`.
    *   **Borrado MD:** Añadir icono de papelera (Lucide `file-minus` o `trash-2`) pequeño junto al link de "Markdown". Debe disparar una confirmación `confirm()` antes de llamar al nuevo endpoint de borrado.

---

## 6. Estrategia de Verificación (Testing)

### A. Tests Unitarios (Backend)
*   Verificar que `clear_story_artifacts` borra exactamente los beats de la historia indicada y no otros.
*   Verificar que la transacción se revierte si ocurre un error a mitad del borrado.

### B. Tests de Integración (Frontend)
*   Verificar que el handler de borrado de MD falla con 404 si el archivo no existe físicamente, pero aun así limpia la DB si el usuario lo solicita (resiliencia).

### C. Pruebas Manuales (E2E)
1.  **Regeneración:** Historia Completa -> Editar Título -> Generar -> Verificar que los beats antiguos desaparecieron de la sala de streaming y de la DB.
2.  **Borrado Parcial:** Galería -> Borrar Markdown -> Recargar -> Verificar que el link desapareció pero la historia y su configuración siguen presentes.

---

## 7. Criterios de Aceptación (Checklist)

- [ ] `SQLStoryRepository` cuenta con método transaccional de limpieza de artefactos.
- [ ] `StreamingService` realiza un reinicio limpio automáticamente al re-generar.
- [ ] Endpoint de borrado de Markdown implementado y funcional en el Frontend.
- [ ] El archivo físico `.md` se elimina del disco al solicitar "Borrar Markdown".
- [ ] La etiqueta "Completada" vuelve a ser visible en la galería y detalle.
- [ ] El botón "Editar" es accesible para historias finalizadas.
- [ ] Se mantiene el principio DRY reutilizando la lógica de resolución de paths.

---
*Este Spec define un estándar de robustez y flexibilidad para la gestión de la producción narrativa en NarrativeForge.*
