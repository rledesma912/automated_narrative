# Spec-220: Motor de Autoría (Wizard y Configuración)

## 1. El Wizard de 5 Pasos
El proceso de creación de historias se guía a través de un stepper interactivo que captura la configuración semántica rica de la narrativa.

### Estructura de Pasos:
1.  **Configuración:** Título, género, subgénero y tono atmosférico.
2.  **Personajes:** Elenco dinámico (hasta 5 protagonistas) con roles y rasgos. Selección del narrador (storyteller).
3.  **Voz:** Configuración avanzada del estilo narrativo (percepción, conocimiento, lenguaje, sesgo).
4.  **Mundo:** Lista dinámica de escenarios (hasta 5) y reglas del mundo.
5.  **Trama:** Definición de la sinopsis estructurada en **5 Actos** (basados en la Pirámide de Freytag: Exposición, Acción Ascendente, Clímax, Acción Descendente y Desenlace).

## 2. Lógica del Stepper y Persistencia
- **Navegación No Lineal:** El usuario puede volver a cualquier paso anterior haciendo clic en los indicadores del stepper, siempre que ya los haya alcanzado.
- **Persistencia Temprana:** Al avanzar del Paso 5 a la pantalla de confirmación, los datos se guardan automáticamente en la base de datos (POST si es nueva, PATCH si es edición) en estado `DRAFT`.
- **Rehidratación:** El botón "Editar" en la galería carga una historia existente en el Wizard, mapeando el JSON de `storyteller_config` a los campos del formulario.

## 3. Definición Dinámica (UI Definitions)
El archivo `ui_definitions.yaml` es la fuente de verdad única para los formularios:
- Define tipos de campos (text, textarea, select, multi-select, radio).
- Contiene las etiquetas, subtítulos y notas explicativas.
- Gestiona las validaciones y los valores por defecto.

## 4. Bidireccionalidad YAML (CLI ↔ Wizard)
El sistema mantiene una paridad total entre el Wizard y el formato YAML para el CLI:
- **YAML Canónico:** Refleja exactamente la estructura del `storyteller_config`.
- **Parser Robusto:** El `MarkdownStoryParser` (ahora orientado a YAML) asegura que las historias creadas por CLI se puedan editar en el Wizard sin pérdida de campos.
- **Exportación:** Comando CLI `export-yaml` para volcar cualquier historia de la base de datos a un archivo editable que puede ser re-importado.

## 5. Refinamientos de UX
- **Listas Dinámicas:** Componentes interactivos para agregar/eliminar personajes y escenarios con modales de confirmación.
- **Edición Universal:** Acceso a edición disponible para historias en estado `completed` (regeneración con cambios).
- **Validación de Reglas:** Corrección de duplicidades en campos y ordenamiento garantizado en el guardado.

---
*Este documento unifica las especificaciones 202, 203, 204, 210, 213, 214 y 217.*
