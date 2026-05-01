# Spec-211: Observabilidad, Footer de Estado y Gestión de Exportaciones

## 1. Contexto y Problema
El sistema actual de generación tiene opacidad en su estado interno. Los logs son escuetos y la gestión de archivos exportados (Markdown) no es intuitiva para el usuario final (falta de links directos en galería y errores de persistencia en la UI).

## 2. Objetivos
1.  **Observabilidad:** Mejorar los logs del backend para identificar conflictos de estado y errores de streaming en tiempo real.
2.  **UI de Estado:** Añadir un footer global en la aplicación que muestre la historia actualmente en proceso.
3.  **Gestión de Descargas:** Corregir el bug que oculta el botón de descarga y habilitar visualización amigable para historias ya generadas.
4.  **UX Galería:** Simplificar la interfaz retirando estados innecesarios en las cards.

---

## 3. Cambios Técnicos

### Slice B1: Mejora de Observabilidad (Backend)
*   **Log mejorado:** En `src/presentation/routers/stream_router.py`, registrar logs detallados al iniciar, finalizar y en caso de conflictos (409) o fallos de stream, incluyendo el ID de historia.
*   **Contexto:** Incluir el estado de la DB en el momento del log.

### Slice F1: Footer de Estado Global
*   **UI:** Añadir un nuevo componente parcial `footer.ejs` (o incluir en `layout.ejs`) que consulte un endpoint global o estado de sesión para mostrar: "Generando: [Título]..." si hay un stream activo.

### Slice F2: Corrección de Descarga y Visualización (Frontend)
*   **Botón Descarga:** Revisar la lógica en `streaming-room.ejs` para asegurar que el botón aparezca al recibir el evento `done`.
*   **Visualización:** Habilitar link "Ver Markdown" en la galería si existe `file_path`. Crear vista `visualizar_markdown.ejs` para presentar el contenido con la estética de la app.

### Slice F3: Limpieza de Galería
*   **Galería:** Modificar `gallery.ejs` para quitar la etiqueta "Completa". El indicador de éxito será la presencia del enlace para "Ver" o "Descargar".

---

## 4. Criterios de Aceptación (Checklist)
- [ ] Logs de API muestran contexto completo de la solicitud de stream.
- [ ] Footer de estado presente en todas las páginas cuando hay un stream en curso.
- [ ] Botón "Descargar Markdown" persiste correctamente tras la generación.
- [ ] Enlace "Ver Markdown" disponible en galería para historias finalizadas.
- [ ] Estado "Completa" eliminado de las tarjetas de galería.

---
*Este Spec mejora drásticamente la capacidad de diagnóstico y la usabilidad de las historias generadas.*
