<!-- variante: frontier | rol: mapper (user, map global) | cargado por: build_synopsis_mapper_prompt() -->
# TAREA DEL DRAMATURGO

Analizas sinopsis narrativas e identificas qué ocurre en cada momento del arco
dramático. Tu producto son {num_beats} frases, una por acto, que describen con
precisión qué sucede en la sinopsis durante ese momento.

## Historia

- Título: {title}
- Narrador: {relator}
- Protagonistas: {protagonistas}
- Escenarios: {escenarios}
- Atmósfera: {atmosfera}
- Reglas: {reglas}

## Sinopsis completa

{sinopsis}

## Análisis narrativo previo

{narrative_brief}

## Estructura de actos

{beats_spec_compact}

## Instrucciones

Para cada acto:
- Identifica en la sinopsis el pasaje que corresponde a ese momento narrativo.
- Escribe UNA oración que describe qué ocurre, usando los eventos y personajes
  reales de la sinopsis. No inventes nada que no esté en ella.
- Si la sinopsis no detalla explícitamente ese acto, infiere la conclusión lógica
  más coherente con lo que sí describe.

Responde SOLO con {num_beats} líneas numeradas:
1. [oración del acto 1 extraída de la sinopsis]
2. [oración del acto 2 extraída de la sinopsis]
