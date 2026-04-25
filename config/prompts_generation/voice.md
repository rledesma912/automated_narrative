<!-- variante: frontier | rol: voz (user) | cargado por: build_beat_prompt() via _voice_template_path() -->
# INSTRUCCIONES DE VOZ - NARRACIÓN DE BEAT

## HISTORIA BASE
- Título: {title}
- Relator: {relator}
- Persona gramatical: {persona_gramatical}
- Atmósfera: {atmosphere}
- Protagonistas: {protagonistas}
- Escenarios: {escenarios}
- Sinopsis: {sinopsis}

## BEAT ACTUAL
- Numero: {beat_number} de {total_beats}
- Resumen: {beat_summary}
- Restricciones dramáticas:
{beat_spec}

{context_section}

## REGLAS DE LA HISTORIA
{reglas}

## INSTRUCCIONES OBLIGATORIAS

### Idioma
- ESCRIBE SIEMPRE EN ESPAÑOL. Nunca uses otro idioma.

### Voz y Persona
- Eres {relator}, narrando la historia
- SIEMPRE usa la perspectiva de {relator}
- SIEMPRE escribe en {persona_gramatical}

### Continuidad
- NUNCA repitas la apertura "Me desperte..." o similares
- CONECTA con el beat anterior (1-2 oraciones)
- AVANZA la historia: algo nuevo debe pasar

### Estructura del Beat (flujo interno, NO usar como títulos)
- Comenzá conectando con el beat anterior en 1-2 oraciones, como continuidad natural.
- Desarrollá lo que ocurre en este beat: acciones, percepciones, tensión.
- Cerrá con una transición o cliffhanger que empuje al siguiente beat.
- NUNCA escribas literalmente las palabras "Apertura", "Desarrollo" ni "Cierre".
- NUNCA uses encabezados markdown (`#`, `##`, `###`) ni separadores (`---`, `***`).
- El beat debe fluir como prosa continua, sin secciones visibles.

### Extensión
- 150-300 palabras por beat

### Reglas de personaje
- ANTES de escribir, revisá las REGLAS DE LA HISTORIA definidas arriba.
- Si una regla define el comportamiento de un personaje, reflejalo en sus acciones, diálogos o pensamientos en este beat.
- Las reglas son restricciones activas, no sugerencias opcionales.

### Output
- SOLO prosa narrativa en párrafos, sin comentarios ni meta-texto.
- NUNCA repitas el beat_summary.
- NUNCA digas "Aqui tienes...", "A continuación...", "Espero que te guste..." ni similares.
- NUNCA uses encabezados, listas, viñetas ni formato markdown. Solo párrafos.