# Spec-220: Motor de Autoría (Wizard y Configuración)

> **Reemplazada por Spec-530 (2026-09-25):** el wizard se retiró; las historias se crean y editan en el asistente (`/nuevo`, `/asistente/{id}/…`). El round-trip YAML sigue (exporta dirección, taller y escaleta; importa los YAML viejos ignorando lo eliminado). Queda como registro histórico.

> **Actualizado por Spec-460 §2.5 (2026-09-22):** el wizard ya no genera ni guarda en silencio al pasar el último paso. La confirmación tiene un único "Guardar historia" (`POST /generar/guardar`, errores visibles) y la generación se lanza desde la galería o la ficha como job. Se eliminó `POST /generar/submit`.

> **Actualizado por Spec-450 (2026-09-23):** el paso 4 (*El Mundo*) suma el grupo opcional «La Amenaza»: hasta 3 entidades (la primera es la principal) con naturaleza filtrada por el género del paso 1 (`source: entity_natures`), topes de largo (`maxlength`) y nivel de revelación. Round-trip en `storyteller_config.entities` (wizard, API, `export-yaml` / `import-yaml`, `generate --input`).

> **Actualizado por Spec-440 (2026-09-23):**
> - **Géneros:** el catálogo vive en la DB (`genre`/`subgenre`, FK compuesta en `story`) y el wizard lo lee de `GET /api/v1/catalog/genres`. Subgénero dependiente del género (`source: genre_catalog`, `depends_on`); par inválido → 422.
> - **Narrador:** el combo "quién cuenta la historia" lista solo personajes con nombre (`source: characters`), se preselecciona si hay uno solo y se valida en el POST del paso.
> - **Rasgos:** lista única con ancla YAML (`&character_traits`), 18 rasgos (se sumaron miedoso, curioso, impulsivo y desconfiado).
> - **Contrato:** la sesión y el DTO al Core usan IDs limpios (`genero`, `subgenero`, `tono`, `narrator_config`); la rehidratación acepta el formato legado `"id: Etiqueta"`. Tipos de regla = `RuleType` del dominio.
> - **Edición:** se pueden editar historias ya generadas; lo generado se conserva hasta regenerar. Con un job activo → 409.
> - **Layout:** wizard compacto para 1080p (`width: half` para campos que comparten fila).
> - **YAML:** `import-yaml` (crea borradores) y `export-yaml --all` completan el round-trip.


## 1. El Wizard de 5 Pasos
El proceso de creación de historias se guía a través de un stepper interactivo que captura la configuración semántica rica de la narrativa.

### Estructura de Pasos:
1.  **Configuración:** Título, género, subgénero y tono atmosférico.
2.  **Personajes:** Elenco dinámico (hasta 5 protagonistas) con roles y rasgos. Selección del narrador (storyteller).
3.  **Voz:** Configuración avanzada del estilo narrativo (percepción, conocimiento, lenguaje, sesgo).
4.  **Mundo:** Lista dinámica de escenarios (hasta 4) y reglas del mundo (hasta 7).
5.  **Trama:** Definición de la sinopsis estructurada en **5 Actos** (basados en la Pirámide de Freytag: Exposición, Acción Ascendente, Clímax, Acción Descendente y Desenlace).

## 2. Lógica del Stepper y Persistencia
- **Navegación No Lineal:** El usuario puede volver a cualquier paso anterior haciendo clic en los indicadores del stepper, siempre que ya los haya alcanzado.
- **Persistencia:** cada campo se auto-guarda en la sesión (`PATCH /generar/paso/:n/guardar`). En la base se guarda recién con "Guardar historia" en la confirmación (POST si es nueva, PATCH si es edición), en estado `DRAFT` (Spec-460 §2.5).
- **Rehidratación:** El botón "Editar" en la galería carga una historia existente en el Wizard, mapeando el JSON de `narrator_config` a los campos del formulario.

## 3. Definición Dinámica (UI Definitions)
El archivo `ui_definitions.yaml` es la fuente de verdad única para los formularios:
- Define tipos de campos (text, textarea, select, multi-select, radio).
- Contiene las etiquetas, subtítulos y notas explicativas.
- Gestiona las validaciones y los valores por defecto.

## 4. Bidireccionalidad YAML (CLI ↔ Wizard)
El sistema mantiene una paridad total entre el Wizard y el formato YAML para el CLI:
- **YAML Canónico:** Refleja exactamente la estructura del `narrator_config` (depurado de `storyteller_config`).
- **Parser Robusto:** El `MarkdownStoryParser` (ahora orientado a YAML) asegura que las historias creadas por CLI se puedan editar en el Wizard sin pérdida de campos.
- **Exportación:** Comando CLI `export-yaml` para volcar cualquier historia de la base de datos a un archivo editable que puede ser re-importado.

## 5. Refinamientos de UX
- **Listas Dinámicas:** Componentes interactivos para agregar/eliminar personajes y escenarios con modales de confirmación.
- **Edición Universal:** Acceso a edición disponible para historias en estado `completed` (regeneración con cambios).
- **Validación de Reglas:** Corrección de duplicidades en campos y ordenamiento garantizado en el guardado.

---
*Este documento unifica las especificaciones 202, 203, 204, 210, 213, 214 y 217.*
