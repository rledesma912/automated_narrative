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

Salida:
{{
  "initial_state": "...",
  "threat_nature": "...",
  "horror_peak": "...",
  "spatial_anchor": "..."
}}