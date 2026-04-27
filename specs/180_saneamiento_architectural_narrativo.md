# Spec-180: Saneamiento Arquitectural y Desacoplamiento Narrativo

## 1. Problema Narrativo y Técnico
El sistema actual presenta acoplamiento y rigidez en la gestión de la identidad narrativa:
1. **Identidad Acoplada**: `PersonaService` intenta resolver géneros gramaticales mediante listas fijas de nombres, lo cual es ineficiente y no escala.
2. **Lógica de Prompts Monolítica**: `PromptBuilder` utiliza condicionales `if/else` para manejar variantes (compact/frontier), violando el principio de Open/Closed.
3. **Ceguera de Intensidad**: El LLM recibe instrucciones de contenido (`must`), pero carece de contexto sobre la "energía" dramática (`intensity`) y los objetivos de éxito del beat.

## 2. Objetivos de Arquitectura
- **SOLID**: Implementar el patrón **Strategy** para la construcción de prompts.
- **Spec-Driven**: Utilizar `storyteller_config` como la única fuente de verdad para la identidad del narrador.
- **KISS**: Eliminar archivos de configuración redundantes (como listas de nombres).

## 3. Plan de Implementación por Slices

### Slice 1: Desacoplamiento de Identidad Narrativa
- Refactorizar `PersonaService` para que extraiga la perspectiva (`person`) y el tono del `storyteller_config`.
- Eliminar la dependencia de listas de nombres hardcoded.
- Implementar fallbacks inteligentes basados en los metadatos de la historia.

### Slice 2: Prompt Strategy Pattern
- Implementar `IPromptStrategy` y sus variantes (`Compact`, `Frontier`).
- Desacoplar la selección de plantillas y el formateo de contexto del `PromptBuilder`.

### Slice 3: Contrato de Resonancia Completo
- Inyectar `intensity`, `state_change` y `success_signal` en los prompts de VOZ.
- Asegurar que el Acto 5 reciba explícitamente la instrucción de baja intensidad y cierre emocional.

### Slice 4: Saneamiento de Servicios Secundarios
- Parametrizar constantes en `SynopsisSliceResolver`.
- Limpiar interfaces de servicios para evitar el uso de métodos privados desde los casos de uso.

## 4. Definición de Hecho (DoD)
- [ ] `PersonaService` resuelve la perspectiva gramatical usando `storyteller_config`.
- [ ] No existen listas de nombres masculinos/femeninos en el código.
- [ ] `PromptBuilder` delega el formateo a una estrategia.
- [ ] Los prompts de VOZ incluyen la intensidad configurada en el YAML de beats.
