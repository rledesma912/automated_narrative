<!-- variante: compact | rol: story_analyst (user) | cargado por: build_story_analyst_prompt() -->
PROTAGONISTAS: {protagonistas}
ESCENARIO: {escenarios}
ATMÓSFERA: {atmosfera}

SINOPSIS:
{sinopsis}

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
[estado emocional y situacional sólo del narrador al inicio del relato]

## threat_nature
[naturaleza exacta del horror — qué es y cómo opera en esta historia concreta]

## horror_peak
[el evento paranormal o de máximo impacto — el momento sin vuelta atrás]

## spatial_anchor
[detalles físicos y sensoriales concretos del lugar donde ocurre el horror]
