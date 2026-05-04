# Spec-230: Ciclo de Vida, Gestión de Historias y Persistencia

## 1. Estados de la Historia
- **DRAFT:** Configuración guardada en el Wizard pero no generada.
- **PROCESSING:** Generación activa mediante streaming SSE.
- **COMPLETED:** Generación finalizada exitosamente.
- **FAILED:** Error durante el proceso o interrupción.

## 2. Persistencia y Exportación
- **Persistencia Incremental:** Los beats narrativos se guardan en la base de datos inmediatamente después de ser generados (`BEAT_DONE`), evitando pérdidas por desconexión.
- **Exportación Automática:** Al finalizar la generación, se crea un archivo Markdown físico.
- **Directorio de Salida Unificado:** La ruta de exportación se centraliza en `Settings.output_dir` (configurable vía `.env`), apuntando por defecto a `frontend/public/output_stories` para servicio estático.

## 3. Gestión del Ciclo de Vida
### Regeneración No Destructiva
- El clic en "Regenerar" desde la galería es informativo y no borra datos; solo prepara la sala de streaming.
- La limpieza real de artefactos previos ocurre solo cuando el usuario confirma activamente el inicio en la sala de streaming.
- **Limpieza Atómica:** Al reiniciar, se eliminan beats, journal, anclajes y el archivo Markdown físico previo de forma coordinada.

### Resiliencia de Estados
- **Recuperación Automática:** Al arrancar el servidor Core, todas las historias que quedaron en estado `processing` (por un crash previo) pasan automáticamente a `failed`.
- **Sala Resiliente:** La sala de streaming funciona en modo lectura para historias `completed` o `failed`, cargando los beats históricos desde la base de datos.

## 4. Gestión de Artefactos (MD)
- **Verificación de Integridad:** La galería verifica la existencia física del archivo Markdown antes de mostrar los links de descarga o visualización.
- **Desvinculación:** Si un archivo Markdown se borra manualmente del disco, la UI permite desvincular el registro en la DB (limpiar `file_path`) desde la vista de visualización.
- **Borrado Físico:** El borrado de una historia desde la galería elimina tanto el registro en la DB (en cascada) como el archivo físico en disco.

## 5. Acciones de Usuario (UX)
- **Hard Delete:** Eliminación total con modal de confirmación HTMX.
- **Visualización Integrada:** Vista dedicada para leer el contenido del Markdown con la estética de la aplicación sin salir de la web.
- **Acceso a Proyectos:** El botón "Ver avance" permite volver a la sala de streaming en cualquier momento para ver los beats generados hasta el momento.

---
*Este documento unifica las especificaciones 205, 212, 218 y 219 (y partes de 214).*
