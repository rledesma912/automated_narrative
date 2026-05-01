# Spec-205: Persistencia, Exportación y UX de Generación

## 1. Contexto y Problema
La experiencia actual de generación presenta debilidades en dos frentes:
1.  **Backend:** Los beats no se persisten incrementalmente durante el streaming (riesgo de pérdida) y no se generan archivos físicos automáticamente.
2.  **Frontend:** Falta de feedback visual durante el guardado de borradores, incertidumbre durante el inicio del streaming (espera del LLM) y una galería de historias incompleta.

## 2. Objetivos
*   **Backend:** Persistencia incremental en DB y exportación automática a `.md`.
*   **Frontend:** Mejorar la UX con notificaciones (popups), indicadores de carga (spinners), un log de progreso para el streaming y gestión completa de la galería.

---

## 3. Parte A: Backend (Refactor de Infraestructura)

### Slice B1: Persistencia Incremental en DB
*   **Implementación:** Inyectar `beat_repo` como parámetro en la función `stream_story()` de `src/application/services/streaming_service.py` (consistente con `story_repo`).
*   **Acción:** Al recibir un `BEAT_DONE`, llamar inmediatamente a `beat_repo.save(macro_beat, story.id)`.

### Slice B2: Servicio de Exportación y Base de Datos
*   **Exportación:** Los archivos MD deben guardarse en `frontend/public/output_stories/`.
*   **Persistencia:** La columna `file_path` en la tabla `story` guardará el path **relativo** (ej: `output_stories/titulo_fecha.md`) para ser servido estáticamente.
*   **Base de Datos:** Se seguirá la regla del proyecto: actualizar `init_db()` en `src/infrastructure/database/connection.py`, borrar `stories.db` y recrear la tabla con la nueva columna `file_path`. No se requiere preservación de datos de desarrollo.

---

## 4. Parte B: Frontend (Refactor de UX/UI)

### Slice F1: Feedback de Guardado (Drafts)
*   **Implementación:** Cambiar el flujo de guardado de borrador a **AJAX (fetch)**. 
*   **UX:** Mostrar un Toast/Globo tras el éxito del guardado y luego redirigir mediante JavaScript. Esto permite una transición suave y feedback inmediato.

### Slice F2: Spinner e Indicador de Inicio de Streaming
*   **Implementación:** Mostrar un spinner prominente en `streaming-room.ejs` desde el momento en que se establece la conexión SSE, ocultándolo solo cuando llegue el primer evento informativo.

### Slice F3: Log de Progreso Estilo CLI
*   **UX:** La sala de streaming **no mostrará el texto narrado**. Solo mostrará una consola de progreso con timestamps (ej: `[10:05] ✍️ Narrando Beat 2/5...`).
*   **Finalización:** Al terminar, mostrar un panel con un botón destacado: "Ver Historia Completa" (redirige a `/historia/{id}`) y "Descargar Markdown" (enlace al archivo físico).

### Slice F4: Gestión de Galería (Eliminar)
*   **Acción:** Implementar **Hard Delete** en la DB (borrado de fila y cascada).
*   **Limpieza:** Se debe eliminar físicamente el archivo `.md` asociado en disco al borrar la historia para evitar acumulación de basura.
*   **Confirmación:** Modal obligatorio de confirmación antes de proceder.

---

## 5. Criterios de Aceptación (Checklist)

### Backend
- [ ] Beats persistidos incrementalmente (verificable via SQLite durante el stream).
- [ ] Archivo `.md` generado físicamente en `frontend/public/output_stories/`.
- [ ] Columna `file_path` con ruta relativa funcional.

### Frontend
- [ ] Toast funcional vía AJAX al guardar borradores.
- [ ] Spinner visible durante la espera inicial del LLM.
- [ ] Sala de streaming limpia (solo log de progreso).
- [ ] Eliminación de historia borra tanto DB como archivo físico.

---
*Este documento consolida las decisiones técnicas para una implementación quirúrgica y coherente.*


