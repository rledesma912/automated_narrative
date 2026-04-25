# Debug Session — NarrativeForge
**Generado:** 2026-04-22 02:05  
**Perfil activo:** ollama-qwen25-14b  
**Provider:** ollama  
**Duración total:** 0.0 s  
**Story ID:** 7ddcef18-a884-4231-b65d-b4657efcb0ac  

---

## Parámetros de la Historia

| Campo | Valor |
|---|---|
| Título | Test |
| Protagonista | X |
| Sinopsis | y |
| Atmósfera | z |
| Relator | tercera |

---

## Llamada 1 — STORY_ANALYST —

### Componente
`StoryAnalystService (story_analyst_service.py)`

### Parámetros de Inferencia

| Param | Valor |
|---|---|
| model | `qwen2.5:14b` |
| temperature | 0.3 |
| num_ctx | 6144 |
| num_predict | 700 |

### System Prompt
```
Sos un analista de narrativa de terror especializado en extracción estructurada.

Tu tarea consiste en mapear sinopsis a un esquema fijo de anclajes narrativos.

DEFINICIÓN DE ANCLAJES:

- initial_state:
  Estado inicial del protagonista antes del horror.
  Incluye situación concreta y estado emocional.

- threat_nature:
  Naturaleza del horror.
  Debe especificar:
  - qué es (entidad, fenómeno, condición)
  - cómo opera sobre el protagonista

- horror_peak:
  Evento de máximo impacto irreversible.
  Punto donde ocurre el horror central o la revelación clave.

- spatial_anchor:
  Lugar físico donde ocurre el horror.
  Debe incluir detalles sensoriales concretos (no genéricos).

REGLAS:
- No inventés información.
- No completes datos ausentes.
- Usá solo información provista.
- Preferí detalles concretos sobre abstracciones.
- Cada campo debe ser específico y verificable en el input.
- Respondé únicamente con las secciones Markdown pedidas, sin texto adicional.
```

### Prompt Enviado
```
PROTAGONISTAS: X
ESCENARIO: ['casa']
ATMÓSFERA: z

SINOPSIS:
y

TAREA:
Extraer los anclajes narrativos definidos en el system prompt.

FUENTES (todas obligatorias):
- SINOPSIS
- PROTAGONISTAS
- ESCENARIO
- ATMÓSFERA

Reglas:
- Debés usar TODAS las fuentes.
- Si un dato aparece fuera de la sinopsis, debe incorporarse igual.
- Está prohibido ignorar PROTAGONISTAS, ESCENARIO o ATMÓSFERA.
- Si la respuesta puede generarse solo con la SINOPSIS, es incorrecta.

Restricciones por campo:
- initial_state → PROTAGONISTAS + SINOPSIS
- threat_nature → SINOPSIS + ATMÓSFERA
- horror_peak → SOLO SINOPSIS
- spatial_anchor → ESCENARIO + SINOPSIS

Respondé ÚNICAMENTE con este formato, sin texto antes ni después:

## initial_state
[estado emocional y situacional del narrador al inicio del relato]

## threat_nature
[naturaleza exacta del horror — qué es y cómo opera en esta historia concreta]

## horror_peak
[el evento paranormal o de máximo impacto — el momento sin vuelta atrás]

## spatial_anchor
[detalles físicos y sensoriales concretos del lugar donde ocurre el horror]
```

### Respuesta Raw
```
Contenido de ejemplo
```

### Respuesta Normalizada
```
Contenido de ejemplo
```

### Resultado del Parser
**Estado:** OK: 4 anclajes  
**Raw chars:** 20 | **Norm chars:** 20 | **Diferencia:** 0.0%

### Timing
- Elapsed LLM: 0.00 s

---

## Llamada 2 — RULE_RESOLVER —

### Componente
`RuleScenarioResolverService`

### Parámetros de Inferencia

| Param | Valor |
|---|---|
| model | `qwen2.5:14b` |
| temperature | 0.2 |
| num_ctx | 6144 |
| num_predict | 700 |

### System Prompt
```
Eres un Estratega Narrativo. Tu tarea es asignar reglas de comportamiento y escenarios detallados a los actos de una historia.

Debes ser extremadamente fiel al input del usuario.
No inventes reglas nuevas.
No resumas las descripciones de los escenarios; úsalas íntegras.

Tu objetivo es que el narrador sepa exactamente qué reglas aplicar en cada momento y en qué lugar exacto transcurre la acción.
```

### Prompt Enviado
```
SINOPSIS:
y

REGLAS DEL USUARIO:
Ninguna

ESCENARIOS DETALLADOS:
0. casa

ACTOS:
Acto 1 (exposicion): establecer normalidad y sembrar una fisura
Acto 2 (accion_ascendente): activar el conflicto mediante transgresion
Acto 3 (climax): forzar reconocimiento del horror
Acto 4 (accion_descendente): llevar al protagonista al colapso y reaccion
Acto 5 (desenlace): cerrar con escape incompleto y secuela

TAREA:
Asigná a cada uno de los 5 actos:
1. Las reglas de usuario que deben estar ACTIVAS y presentes en la mente del narrador durante ese acto.
2. El índice del escenario (0 a N) donde ocurre ese acto.

REGLAS DE ASIGNACIÓN:
- Una regla puede estar en varios actos o en uno solo.
- Si una regla es sobre el escepticismo inicial, solo ponela en los actos donde el personaje deba ser escéptico.
- El escenario_index debe corresponder al orden en la lista de ESCENARIOS DETALLADOS.

RESPONDE ÚNICAMENTE CON ESTE JSON:
{
  "1": { "rules": ["Regla exacta", ...], "scenario_index": 0 },
  "2": { "rules": [...], "scenario_index": 1 },
  ...
}
```

### Respuesta Raw
```
Contenido de ejemplo
```

### Respuesta Normalizada
```
Contenido de ejemplo
```

### Resultado del Parser
**Estado:** OK: 5 actos mapeados  
**Raw chars:** 20 | **Norm chars:** 20 | **Diferencia:** 0.0%

### Timing
- Elapsed LLM: 0.00 s

---

## Llamada 3 — MAPPER Beat #1

### Componente
`SynopsisBeatMapper (synopsis_beat_mapper.py)`

### Parámetros de Inferencia

| Param | Valor |
|---|---|
| model | `qwen2.5:14b` |
| temperature | 0.4 |
| num_ctx | 6144 |
| num_predict | 700 |

### System Prompt
```
Tu output será usado por un narrador en primera persona para escribir prosa literaria.
Ese narrador conoce la atmósfera y los personajes, pero no sabe qué eventos concretos ocurren en cada momento del relato.

Sos un extractor de sinopsis. Tu tarea es segmentar el texto en fragmentos ordenados, agrupando los eventos concretos por momento narrativo. No inventés, no expandás, no interpretés.
```

### Prompt Enviado
```
SINOPSIS COMPLETA:
y

ESCENARIOS CRONOLÓGICOS:
- casa

ANCLAJE PRINCIPAL: y
ANCLAJE DE CONTEXTO: y

ACTO 1 — exposicion: establecer normalidad y sembrar una fisura

Extraé la información de este acto a partir de la sinopsis.

1. Identificá qué escenario de la lista corresponde a este acto.
2. Extraé todos los eventos concretos de la sinopsis que pertenecen a este acto.

No inventés. No expandás. Solo lo que está escrito en el texto.

FORMATO (seguilo exactamente, sin texto adicional antes ni después):

ESCENARIO: [nombre exacto de uno de los escenarios de la lista]

EVENTOS:
- [primer evento concreto del acto, en orden narrativo]
- [segundo evento concreto del acto]
```

### Respuesta Raw
```
Contenido de ejemplo
```

### Respuesta Normalizada
```
Contenido de ejemplo
```

### Resultado del Parser
**Estado:** ok: escenario='casa', summary=20 chars  
**Raw chars:** 20 | **Norm chars:** 20 | **Diferencia:** 0.0%

### Timing
- Elapsed LLM: 0.00 s

---

## Llamada 4 — VOZ Beat #1

### Componente
`VozUseCase (voz_use_case.py)`

### Parámetros de Inferencia

| Param | Valor |
|---|---|
| model | `qwen2.5:14b` |
| temperature | 0.6 |
| num_ctx | 6144 |
| num_predict | 600 |

### Narrative Context (pre-baked)
```
ACTO: exposicion — establecer normalidad y sembrar una fisura
ARCO EMOCIONAL: estabilidad → incomodidad leve

ESCENARIO ACTIVO:
casa

ESCENARIO DETALLADO (Input Usuario):
casa

EVENTO DE ESTE MOMENTO:
Contenido de ejemplo

ANCLAJE PRINCIPAL:
y

ANCLAJE DE CONTEXTO:
y

RESTRICCIONES:
Debe incluir: presentar situacion base del narrador / introducir una anomalia sutil / incluir regla, advertencia o limite implicito
PROHIBIDO: confirmar lo paranormal
Objetivo: quien escucha el relato percibe que algo no encaja pero no sabe que
```

### System Prompt
```
Sos tercera, narrando en primera persona los hechos de la historia.
Atmósfera: z
Personajes: X

Reglas del relato:
Ninguna

INSTRUCCIONES:
- Escribís solo prosa narrativa en español. Sin títulos, sin meta-texto, sin explicaciones.
- No inventés eventos que no estén en el contexto narrativo que recibís.
- No anticipés lo que ocurre en actos posteriores.
- LÍMITE: entre 150 y 200 palabras. Cortá antes de pasarte.
- No rompas el personaje. No repitas lo que ya fue narrado.
```

### Prompt Enviado
```
ACTO: exposicion — establecer normalidad y sembrar una fisura
ARCO EMOCIONAL: estabilidad → incomodidad leve

ESCENARIO ACTIVO:
casa

ESCENARIO DETALLADO (Input Usuario):
casa

EVENTO DE ESTE MOMENTO:
Contenido de ejemplo

ANCLAJE PRINCIPAL:
y

ANCLAJE DE CONTEXTO:
y

RESTRICCIONES:
Debe incluir: presentar situacion base del narrador / introducir una anomalia sutil / incluir regla, advertencia o limite implicito
PROHIBIDO: confirmar lo paranormal
Objetivo: quien escucha el relato percibe que algo no encaja pero no sabe que

Escribí el fragmento del relato para este acto.
```

### Respuesta Raw
```
Contenido de ejemplo
```

### Respuesta Normalizada
```
Contenido de ejemplo
```

### Resultado del Parser
**Estado:** n/a  
**Raw chars:** 20 | **Norm chars:** 20 | **Diferencia:** 0.0%

### Timing
- Elapsed LLM: 0.00 s

---

## Llamada 5 — JOURNAL Beat #1

### Componente
`MemoryJournalist (memory_journalist.py)`

### Parámetros de Inferencia

| Param | Valor |
|---|---|
| model | `qwen2.5:14b` |
| temperature | 0.3 |
| num_ctx | 3072 |
| num_predict | 256 |

### System Prompt
```
Eres un asistente que genera resúmenes narrativos en JSON. Solo respondes con JSON válido, sin markdown ni texto adicional.
```

### Prompt Enviado
```
# GUARDIÁN DE COHERENCIA NARRATIVA

Tu misión es actuar como el "Journalist" del sistema. Después de cada beat, debes extraer y actualizar el estado narrativo para mantener coherencia entre actos.

## CONTEXTO DE LA HISTORIA

- Título: Test
- Protagonistas: X
- Atmósfera: z



## BEAT ACTUAL

### Beat #1: Contenido de ejemplo

### Contenido generado:
Contenido de ejemplo

## INSTRUCCIONES

Analiza el beat generado y actualiza el registro narrativo. Responde SOLO con este JSON exacto:

```json
{
  "last_events": "Qué ocurrió en este beat (1-2 oraciones)",
  "unresolved_mysteries": "Nuevas preguntas, pistas sin resolver o misterios introducidos (o vacío si no hay)",
  "physical_emotional_state": "Cómo quedan los personajes - heridas, estado mental, ubicación actual"
}
```

## REGLAS

- No inventar información que no esté en el beat
- last_action debe ser una acción física o decisión clara (no emociones)

```

### Respuesta Raw
```
Contenido de ejemplo
```

### Respuesta Normalizada
```
Contenido de ejemplo
```

### Resultado del Parser
**Estado:** n/a (JSON interno)  
**Raw chars:** 20 | **Norm chars:** 20 | **Diferencia:** 0.0%

### Timing
- Elapsed LLM: 0.00 s

---

## Llamada 6 — MAPPER Beat #2

### Componente
`SynopsisBeatMapper (synopsis_beat_mapper.py)`

### Parámetros de Inferencia

| Param | Valor |
|---|---|
| model | `qwen2.5:14b` |
| temperature | 0.4 |
| num_ctx | 6144 |
| num_predict | 700 |

### System Prompt
```
Tu output será usado por un narrador en primera persona para escribir prosa literaria.
Ese narrador conoce la atmósfera y los personajes, pero no sabe qué eventos concretos ocurren en cada momento del relato.

Sos un extractor de sinopsis. Tu tarea es segmentar el texto en fragmentos ordenados, agrupando los eventos concretos por momento narrativo. No inventés, no expandás, no interpretés.
```

### Prompt Enviado
```
SINOPSIS COMPLETA:
y

ESCENARIOS CRONOLÓGICOS:
- casa

ANCLAJE PRINCIPAL: y
ANCLAJE DE CONTEXTO: y

MEMORIA DEL ACTO ANTERIOR:
{"last_events": "", "unresolved_mysteries": "", "physical_emotional_state": ""}

ACTO 2 — accion_ascendente: activar el conflicto mediante transgresion

Extraé la información de este acto a partir de la sinopsis.

1. Identificá qué escenario de la lista corresponde a este acto.
2. Extraé todos los eventos concretos de la sinopsis que pertenecen a este acto.

No inventés. No expandás. Solo lo que está escrito en el texto.

FORMATO (seguilo exactamente, sin texto adicional antes ni después):

ESCENARIO: [nombre exacto de uno de los escenarios de la lista]

EVENTOS:
- [primer evento concreto del acto, en orden narrativo]
- [segundo evento concreto del acto]
```

### Respuesta Raw
```
Contenido de ejemplo
```

### Respuesta Normalizada
```
Contenido de ejemplo
```

### Resultado del Parser
**Estado:** ok: escenario='casa', summary=20 chars  
**Raw chars:** 20 | **Norm chars:** 20 | **Diferencia:** 0.0%

### Timing
- Elapsed LLM: 0.00 s

---

## Llamada 7 — VOZ Beat #2

### Componente
`VozUseCase (voz_use_case.py)`

### Parámetros de Inferencia

| Param | Valor |
|---|---|
| model | `qwen2.5:14b` |
| temperature | 0.6 |
| num_ctx | 6144 |
| num_predict | 600 |

### Narrative Context (pre-baked)
```
ACTO: accion_ascendente — activar el conflicto mediante transgresion
ARCO EMOCIONAL: incomodidad → inquietud concreta

ESCENARIO ACTIVO:
casa

ESCENARIO DETALLADO (Input Usuario):
casa

EVENTO DE ESTE MOMENTO:
Contenido de ejemplo

ANCLAJE PRINCIPAL:
y

ANCLAJE DE CONTEXTO:
y

MEMORIA DEL ACTO ANTERIOR:

RESTRICCIONES:
Debe incluir: romper la regla o ignorar la advertencia / mostrar un evento anomalo concreto / intentar explicacion racional
PROHIBIDO: aceptar lo paranormal como hecho
Objetivo: quien escucha el relato nota que el protagonista duda pero sigue dentro de una logica racional
```

### System Prompt
```
Sos tercera, narrando en primera persona los hechos de la historia.
Atmósfera: z
Personajes: X

Reglas del relato:
Ninguna

INSTRUCCIONES:
- Escribís solo prosa narrativa en español. Sin títulos, sin meta-texto, sin explicaciones.
- No inventés eventos que no estén en el contexto narrativo que recibís.
- No anticipés lo que ocurre en actos posteriores.
- LÍMITE: entre 150 y 200 palabras. Cortá antes de pasarte.
- No rompas el personaje. No repitas lo que ya fue narrado.
```

### Prompt Enviado
```
ACTO: accion_ascendente — activar el conflicto mediante transgresion
ARCO EMOCIONAL: incomodidad → inquietud concreta

ESCENARIO ACTIVO:
casa

ESCENARIO DETALLADO (Input Usuario):
casa

EVENTO DE ESTE MOMENTO:
Contenido de ejemplo

ANCLAJE PRINCIPAL:
y

ANCLAJE DE CONTEXTO:
y

MEMORIA DEL ACTO ANTERIOR:

RESTRICCIONES:
Debe incluir: romper la regla o ignorar la advertencia / mostrar un evento anomalo concreto / intentar explicacion racional
PROHIBIDO: aceptar lo paranormal como hecho
Objetivo: quien escucha el relato nota que el protagonista duda pero sigue dentro de una logica racional

Escribí el fragmento del relato para este acto.
```

### Respuesta Raw
```
Contenido de ejemplo
```

### Respuesta Normalizada
```
Contenido de ejemplo
```

### Resultado del Parser
**Estado:** n/a  
**Raw chars:** 20 | **Norm chars:** 20 | **Diferencia:** 0.0%

### Timing
- Elapsed LLM: 0.00 s

---

## Resumen de Sesión

| # | Rol | Componente | Beat | Modelo | Elapsed | Raw chars | Norm chars | Parser |
|---|---|---|---|---|---|---|---|---|
| 1 | story_analyst | StoryAnalystService (story_analyst_service.py) | — | qwen2.5:14b | 0.0s | 20 | 20 | OK: 4 anclajes |
| 2 | rule_resolver | RuleScenarioResolverService | — | qwen2.5:14b | 0.0s | 20 | 20 | OK: 5 actos mapeados |
| 3 | mapper | SynopsisBeatMapper (synopsis_beat_mapper.py) | 1 | qwen2.5:14b | 0.0s | 20 | 20 | ok: escenario='casa', summary=20 chars |
| 4 | voz | VozUseCase (voz_use_case.py) | 1 | qwen2.5:14b | 0.0s | 20 | 20 | n/a |
| 5 | journal | MemoryJournalist (memory_journalist.py) | 1 | qwen2.5:14b | 0.0s | 20 | 20 | n/a (JSON interno) |
| 6 | mapper | SynopsisBeatMapper (synopsis_beat_mapper.py) | 2 | qwen2.5:14b | 0.0s | 20 | 20 | ok: escenario='casa', summary=20 chars |
| 7 | voz | VozUseCase (voz_use_case.py) | 2 | qwen2.5:14b | 0.0s | 20 | 20 | n/a |
| **TOTAL** | | | | | **0.0s** | | | |
