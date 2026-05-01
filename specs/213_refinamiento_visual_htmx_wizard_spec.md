# Spec-213: Refinamiento Estético, Modales HTMX y Optimización del Wizard

## 1. Visión del Arquitecto (Technical Vision)
Este spec se enfoca en la **madurez visual** y la **resiliencia funcional** del sistema. Pasamos de una UX basada en comportamientos nativos del navegador (modales `confirm`, alertas) a una experiencia integrada y fluida mediante **HTMX** para diálogos asíncronos. Se optimiza la sala de generación eliminando redundancias visuales y se escala la tipografía/espaciado para una lectura más cómoda. Finalmente, se corrige la integridad de datos en el ciclo de edición del Wizard.

### Principios de Diseño:
*   **KISS:** Simplificación de la sala de generación quitando elementos redundantes.
*   **UX Dinámica:** Uso de HTMX para eliminar diálogos bloqueantes del navegador.
*   **Escalabilidad Visual:** Ajuste global de la escala para mejor accesibilidad.

---

## 2. Slices de Implementación

### Slice F1: Escala Global y Estilo (CSS/Theming)
*   Incrementar variables de `font-size` y `padding` en `layout.ejs`.
*   Ajustar ancho de Sidebar y espaciado de contenido principal.

### Slice F2: Modales HTMX (UX Dinámica)
*   Crear parcial `modal_confirm.ejs`.
*   Migrar borrado de historias de galería a HTMX.
*   Mover botón de borrado de Markdown de la galería a `visualizar_markdown.ejs` e integrarlo con modal HTMX.

### Slice F3: Rediseño de Sala de Generación
*   Eliminar la barra de progreso.
*   Aumentar tamaño de los 5 círculos de fase.
*   Añadir labels explicativos debajo de cada círculo (Análisis, Exposición, Acción, Clímax, Resolución).
*   Añadir un "Gran Spinner" central para las esperas iniciales del LLM.

### Slice F4: Fix Wizard y Limpieza de UI
*   Corregir `mapStoryToWizard` en `wizard.service.ts` para asegurar recuperación total de datos.
*   Eliminar el botón "Ver" de la galería (redundante con el Título).

---

## 3. Checklist de Tareas

- [ ] Escalar variables CSS en `layout.ejs`.
- [ ] Eliminar botón "Ver" en `gallery.ejs`.
- [ ] Crear `frontend/src/views/partials/modal_confirm.ejs`.
- [ ] Implementar flujo HTMX para eliminación de historia.
- [ ] Mover borrado de MD a `visualizar_markdown.ejs`.
- [ ] Eliminar barra de progreso en `streaming-room.ejs`.
- [ ] Círculos de fase más grandes y con labels explicativos.
- [ ] Implementar el "Gran Spinner" central en la sala de stream.
- [ ] Corregir bug de recuperación de datos en `wizard.service.ts`.

---
*Este Spec asegura una herramienta de autoría profesional, limpia y visualmente coherente.*
