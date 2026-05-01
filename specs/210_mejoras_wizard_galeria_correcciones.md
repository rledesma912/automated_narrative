# Spec-210: Mejoras de UX en Galería, Wizard y Sala de Generación

## 1. Contexto y Problema
Tras la implementación de la persistencia incremental (Spec-205), han surgido necesidades de refinamiento en la interfaz:
1.  **Galería:** El status "Borrador" es visualmente confuso (parece un botón). Falta acceso directo para editar historias guardadas.
2.  **Wizard:** Errores de duplicación en la definición de campos (Reglas del Mundo) y campos de texto insuficientes para la profundidad de los actos.
3.  **Sala de Generación:** Falta feedback visual continuo mientras el LLM procesa el relato.
4.  **Limpieza:** La vista de componentes ya no es necesaria.

## 2. Objetivos
*   Mejorar la legibilidad de estados en Galería e Historia.
*   Habilitar la edición de historias existentes cargando datos desde la DB al Wizard.
*   Corregir bugs estructurales en `ui_definitions.yaml`.
*   Aumentar el tamaño de los campos de actos para facilitar la escritura.
*   Añadir indicadores de carga dinámicos durante la generación.

---

## 3. Cambios en UI/UX (Frontend)

### Slice F1: Refactor de Etiquetas de Estado
*   **Archivos:** `frontend/src/views/gallery.ejs` y `frontend/src/views/historia.ejs`.
*   **Acción:** Cambiar el estilo de `STATUS_LABEL` para `draft` y `failed`.
*   **Nuevo Diseño:** Eliminar el borde (`border`) y el padding de botón. Usar texto en mayúsculas pequeñas, negrita, con un punto de color o simplemente color de fuente, para que no parezca interactivo.
*   **Consistencia:** Aplicar el mismo criterio en la vista de detalle de historia.

### Slice F2: Edición de Historias (Carga en Wizard)
*   **Galería:** Añadir un enlace "Editar" junto a "Ver" en cada tarjeta de historia (solo si el estado es `draft` o `failed`).
*   **Controlador (`wizard.controller.ts`):** Crear ruta `/generar/cargar/:storyId`.
    *   Lógica: Obtener la historia de la API Core.
    *   Mapear `story.storyteller_config` (que contiene los campos del wizard) al objeto `session.wizard`.
    *   Redirigir a `/generar/paso/1`.
*   **Servicio (`wizard.service.ts`):** Implementar una función helper para realizar este mapeo de forma limpia, asegurando que los arrays (traits, multi-selects) se preserven correctamente.

### Slice F3: Correcciones en Wizard y Trama
*   **Bug Reglas:** Corregir en `frontend/config/ui_definitions.yaml` el campo `rule_3_text` duplicado (cambiar a `rule_4_text`).
*   **Tamaño de Actos:** Actualizar los 5 campos de `step_plot` en `ui_definitions.yaml` para que tengan `rows: 7`.
*   **Orden de Reglas:** Asegurar que la lógica de renderizado en `wizard.ejs` mantenga el orden de los campos dentro del grupo `reglas`.

### Slice F4: Feedback en Sala de Generación
*   **Archivo:** `frontend/src/views/streaming-room.ejs`.
*   **Acción:** Añadir un spinner pequeño (clase `animate-spin`) junto al texto de "Narrando Beat X/5..." en el log de progreso y/o en el badge de estado.
*   **UX:** El usuario debe percibir movimiento constante mientras la conexión SSE esté activa y se esté recibiendo un beat.

### Slice F5: Limpieza de Código (Dead Code)
*   **Eliminar:** `frontend/src/views/components.ejs`.
*   **Rutas:** Eliminar la ruta `/componentes` de `frontend/src/routes/index.ts`.
*   **Controlador:** Eliminar `componentsPage` de `theme.controller.ts`.
*   **Navegación:** Eliminar el enlace a "Componentes" en `frontend/src/views/partials/sidebar.ejs`.

---

## 4. Criterios de Aceptación (Checklist)

- [ ] Los borradores en la galería ya no parecen botones.
- [ ] El botón "Editar" en galería carga correctamente todos los campos previos en el wizard.
- [ ] La Regla 4 del mundo se guarda y muestra por separado de la Regla 3.
- [ ] Los textareas de los 5 actos muestran 7 líneas por defecto.
- [ ] Se visualiza un spinner durante la narración de cada beat.
- [ ] La ruta `/componentes` devuelve 404 y no hay links hacia ella.

---
*Este Spec asegura una transición fluida hacia una herramienta de autoría más profesional y depurada.*
