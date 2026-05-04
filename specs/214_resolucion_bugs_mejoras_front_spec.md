# Spec-214: Resolución de Bugs, Gestión de Estados y Refinamiento de UX (Wizard & Galería)

## 1. Visión del Arquitecto (Technical Vision)
Este pliego de condiciones aborda la **resiliencia del estado de la aplicación** y la **fluidez de la navegación de autoría**. Se busca eliminar la incertidumbre sobre el estado "Generando" mediante mecanismos de recuperación proactiva y mejorar la UX del Wizard permitiendo una navegación no lineal. La persistencia se desplaza hacia la izquierda en el ciclo de vida (Persistencia Temprana) para asegurar que ninguna configuración de usuario se pierda tras la revisión.

### Principios de Diseño:
*   **Idempotencia & Resiliencia:** El sistema debe recuperarse automáticamente de estados inconsistentes (p.ej. historias marcadas como "Generando" tras un reinicio del servidor).
*   **Fail-Fast & Feedback:** Si un recurso (Markdown) no existe, la UI debe ofrecer una solución inmediata (Desvincular) mediante una verificación explícita.
*   **Navegación No Lineal Controlada:** El Wizard permite saltos entre pasos ya alcanzados.
*   **SOLID (Interface Segregation):** Las vistas de detalle y galería segregan responsabilidades de gestión de archivos.

---

## 2. Slice B1: Backend - Resiliencia y Recuperación de Estados
**Objetivo:** Eliminar estados "Generando" fantasmas tras reinicios o caídas.

*   **Repository (`src/infrastructure/database/repositories/story_repository.py`):**
    *   Implementar `recover_processing_stories()`:
        *   Transición masiva de `status = 'processing'` a `status = 'failed'` para todas las historias en la base de datos.
        *   Añadir log de observabilidad: `"Recuperadas N historias en estado inconsistente tras reinicio"`.
*   **Lifespan (`src/main.py`):**
    *   Invocar `repo.recover_processing_stories()` durante el arranque (`lifespan` de FastAPI), justo después de `init_db()`.
*   **Regresión Spec-212 (Fix):**
    *   Asegurar que la lógica de re-generación (re-start) en `StreamingService` limpie correctamente los beats previos si la historia está en estado `failed` o `completed`.

---

## 3. Slice F1: Galería - Verificación de Markdown y Sala Resiliente
**Objetivo:** Mejorar la gestión de errores de archivos y el acceso al progreso.

*   **Endpoint de Verificación (`frontend/src/controllers/historia.controller.ts`):**
    *   Implementar `GET /api/historia/:id/markdown-check`.
    *   Lógica (para Galería):
        1. Consultar `file_path` en la DB (vía Core API).
        2. Si no tiene path -> Retornar parcial de botón "Exportar".
        3. Si tiene path -> Verificar existencia física en disco.
        4. Si existe -> Retornar link normal al Markdown.
        5. **Si NO existe** -> Retornar botón de "Archivo perdido" (enlace rojo, sin acción de desvinculación en galería).
*   **Sala de Generación Resiliente (`streaming-room.ejs`):**
    *   **Modo Dual:**
        *   Si `status === 'processing'`: Comportamiento SSE actual (visualización dinámica).
        *   Si `status === 'completed'` o `'failed'`: **Modo Lectura**. Cargar todos los beats desde la DB al renderizar.
        *   Si `'failed'`: Mostrar un botón destacado de "Regenerar" al final de la lista de beats.
*   **Acceso desde Galería:** El botón "Ver progreso" (ahora renombrado a "**Ver avance**" si no está generando) debe llevar siempre a esta sala.
*   **Desvinculación por archivo perdido:** Se gestiona **exclusivamente** en la página de visualización de Markdown (`visualizar_markdown.ejs`). Si el archivo no existe al cargar la página, se muestra el botón de Desvincular que limpia el `file_path` de la DB.

---

## 4. Slice F2: Wizard - Persistencia Temprana y Navegación
**Objetivo:** Guardar en DB al finalizar el Wizard y permitir navegación por el stepper.

*   **Navegación del Stepper:**
    *   **Regla:** Un paso `N` es clickable si `N <= paso_actual_en_sesion`.
    *   En `wizard.ejs`, los círculos del stepper deben ser `<a>` links si cumplen la regla.
*   **Persistencia Temprana (Step 5 → Confirmación):**
    *   Al hacer click en "**Guardar y revisar**" (último paso):
        1. **Check de Identidad:** Si existe `req.session.wizard_story_id`:
            *   Ejecutar `PATCH /stories/:id` con los datos actuales.
        2. Si NO existe:
            *   Ejecutar `POST /stories` (creación inicial en estado `DRAFT`).
            *   Guardar el `id` resultante en `req.session.wizard_story_id`.
        3. Redirigir a `/generar/confirmar`.
*   **Edición Post-Guardado:** Si el usuario retrocede desde la confirmación al wizard, cualquier "Siguiente" posterior debe usar la lógica de `PATCH` detectando el ID en sesión.

---

## 5. Slice F3: Limpieza de UI (Vista de Historia y Markdown)
**Objetivo:** Simplificar la vista de detalle eliminando redundancia, y mover la desvinculación a la página de Markdown.

*   **Vistas (`historia.ejs`):**
    *   Eliminar el bloque de alerta y el botón de "Desvincular" manual.
    *   Mantener únicamente "Borrar Markdown" (borrado físico + desvinculación) como acción de gestión.
*   **Vista de Markdown (`visualizar_markdown.ejs`):**
    *   Al cargar, verificar si el archivo físico existe.
    *   **Si NO existe**: Mostrar botón "Desvincular registro" que llama al endpoint para limpiar `file_path` en la DB.
    *   **Si existe**: Mostrar botón "Eliminar Archivo" (borrado físico + desvinculación) como acción de gestión.

---

## 6. Criterios de Aceptación (Checklist)

- [ ] Las historias `processing` pasan a `failed` automáticamente al reiniciar el Core.
- [ ] Endpoint `/markdown-check` implementado y usado en la Galería para verificar integridad.
- [ ] La sala de streaming muestra beats históricos si la historia ya terminó o falló.
- [ ] El Wizard persiste los datos (POST o PATCH) al pasar del paso 5 a Confirmación.
- [ ] El stepper permite volver a pasos anteriores (<= actual).
- [ ] "Desvincular" solo aparece en la página de Markdown (`visualizar_markdown.ejs`) si el archivo MD fue borrado del disco.
- [ ] La regeneración desde estado `failed` limpia artefactos previos (Fix Regresión Spec-212).

---
*Este Spec asegura la integridad del ciclo de vida de la historia y mejora significativamente la robustez del sistema ante fallos externos.*
