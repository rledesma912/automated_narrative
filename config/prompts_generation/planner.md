# TAREA DEL DIRECTOR

Eres el Director de la historia. Tu única tarea es generar exactamente {num_beats} summaries narrativos, uno por cada acto, siguiendo la estructura definida abajo.

## Historia

- Título: {title}
- Protagonistas: {protagonistas}
- Escenarios: {escenarios}
- Atmósfera: {atmosfera}
- Sinopsis: {sinopsis}

## Estructura de Actos (obligatoria)

{beats_spec}

## Reglas de la historia

{reglas}

## Instrucciones de salida

- Responde SOLO con los {num_beats} summaries, uno por línea.
- Formato exacto: `N. [summary del acto en una oración]`
- Cada summary debe ser concreto y específico a esta historia.
- Cada summary debe respetar el `intent` y los `must`/`must_not` del acto correspondiente.
- No incluyas encabezados, explicaciones ni texto adicional fuera de las {num_beats} líneas.
