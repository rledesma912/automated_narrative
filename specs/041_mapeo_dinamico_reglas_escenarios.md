# SPEC-041: Mapeo Dinámico de Reglas y Escenarios Detallados

**Estado:** APROBADO  
**Fecha:** 2026-04-21  
**Rama destino:** `feature/rule-scenario-resolver`  

## 1. Problema y Motivación

Los modelos de lenguaje pequeños (Ollama, Mistral, Llama 3) sufren de **ceguera de contexto** cuando se les entrega una gran cantidad de reglas globales en el System Prompt. Tienden a priorizar la generación de la escena actual e ignorar restricciones de comportamiento de largo aliento (ej: "Ricardo debe ser escéptico hasta el Acto 3").

Además, la arquitectura actual (Spec 038) tiene una debilidad en la gestión de **escenarios cronológicos**: el `DirectorUseCase` simplifica los escenarios definidos por el usuario a un simple nombre, perdiendo toda la riqueza sensorial (olores, texturas, ruidos) que el usuario detalló en el input.

## 2. Objetivo

Introducir una fase de **Resolución de Estrategia Narrativa** dedicada, separada de la extracción de anclajes y del mapeo de eventos, que asigne específicamente cada regla de usuario y cada descripción detallada de escenario al acto (Macro-Beat) donde debe manifestarse.

## 3. Nuevo Flujo de Planificación

El pipeline de planificación global se expande a tres pasos antes de iniciar la narración:

1.  **StoryAnalyst (Fase 1 - Existente):** Extrae `NarrativeAnchors` (pilares estructurales).
2.  **RuleScenarioResolver (Fase 2 - NUEVO):** 
    *   **LLM Call:** Una llamada dedicada con su propio system prompt.
    *   **Entrada:** Sinopsis + Lista de Reglas + Escenarios Detallados (User Input).
    *   **Tarea:** Mapear qué reglas aplican a qué actos y qué escenario detallado corresponde a cada acto.
    *   **Salida:** Mapa de instrucciones de usuario por acto.
3.  **SynopsisBeatMapper (Fase 3 - Existente):** Extrae el evento (summary) para cada acto.

## 4. Diseño del RuleScenarioResolver

### 4.1 Entrada y Salida
El resolver debe recibir la lista numerada de reglas y escenarios del usuario. Debe devolver un objeto estructurado (JSON) que facilite la distribución determinística.

**Esquema de Salida Sugerido:**
```json
{
  "1": {
    "rules": ["Ricardo ignora lo sobrenatural", "La atmósfera debe ser opresiva"],
    "scenario_index": 0
  },
  "2": {
    "rules": ["Ricardo ignora lo sobrenatural", "Introducir ruidos mecánicos"],
    "scenario_index": 1
  },
  ...
}
```

### 4.2 Lógica de Distribución
- Una regla puede aplicarse a múltiples actos (ej: escepticismo inicial).
- El `scenario_index` apunta a la posición original en la lista `cronologic_scenarios` del usuario.

## 5. Cambios en el Modelo y Contexto

### 5.1 MacroBeat (Dominio)
Se deben añadir campos para persistir esta resolución:
- `active_rules`: Lista de reglas de usuario seleccionadas para este acto.
- `active_scenario_description`: El texto completo del escenario definido por el usuario (no solo el nombre).

### 5.2 Ensamblado del Narrative Context (PromptBuilder)
El contexto que recibe el agente de **VOZ** se reforzará con estas secciones ineludibles:

```markdown
## REGLAS DE USUARIO PARA ESTE ACTO
- [Regla 1]
- [Regla 2]

## ESCENARIO DETALLADO (Input del Usuario)
[Descripción sensorial completa: olores, luces, sonidos]
```

Estas secciones se colocarán en la parte superior del prompt de usuario para el VOZ, dándoles la máxima prioridad operativa.

## 6. Criterios de Aceptación

1.  **Aislamiento:** El Analista de Anclajes no debe encargarse de las reglas para evitar sobrecarga y alucinación.
2.  **Fidelidad Sensorial:** El agente de VOZ debe recibir la descripción original del usuario para el escenario, no una versión resumida.
3.  **Operatividad:** El sistema debe ser capaz de "apagar" una regla en actos posteriores (ej: cuando el personaje finalmente acepta el horror).
4.  **Trazabilidad:** El archivo de debug (`--debug`) debe mostrar claramente qué reglas y qué descripción de escenario se asignaron a cada beat.
