# Debug Session — NarrativeForge
**Generado:** 2026-04-22 02:04  
**Perfil activo:** ollama-qwen25-14b  
**Provider:** ollama  
**Duración total:** 0.0 s  
**Story ID:** 3269f353-5008-406d-94dd-4a0ff59cfe2e  

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

## Resumen de Sesión

| # | Rol | Componente | Beat | Modelo | Elapsed | Raw chars | Norm chars | Parser |
|---|---|---|---|---|---|---|---|---|
| 1 | story_analyst | StoryAnalystService (story_analyst_service.py) | — | qwen2.5:14b | 0.0s | 20 | 20 | OK: 4 anclajes |
| **TOTAL** | | | | | **0.0s** | | | |
