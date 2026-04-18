# GUARDIÁN DE COHERENCIA NARRATIVA

Tu misión es actuar como el "Journalist" del sistema. Después de cada beat, debes extraer y actualizar el estado narrativo para mantener coherencia entre actos.

## CONTEXTO DE LA HISTORIA

- Título: {title}
- Protagonistas: {protagonistas}
- Atmósfera: {atmosfera}

## ESTADO ANTERIOR (del beat anterior)

- Últimos eventos: {prev_last_events}
- Misterios sin resolver: {prev_unresolved_mysteries}
- Estado físico/emocional: {prev_physical_emotional_state}

## BEAT ACTUAL

### Beat #{beat_number}: {beat_summary}

### Contenido generado:
{beat_content}

## INSTRUCCIONES

Analiza el beat generado y actualiza el registro narrativo. Responde SOLO con este JSON exacto:

```json
{{
  "last_events": "Qué ocurrió en este beat (1-2 oraciones)",
  "unresolved_mysteries": "Nuevas preguntas, pistas sin resolver o misterios introducidos (o vacío si no hay)",
  "physical_emotional_state": "Cómo quedan los personajes - heridas, estado mental, ubicación actual"
}}
```

## REGLAS

- No inventar información que no esté en el beat
- Mantener consistencia con el estado anterior
- last_action debe ser una acción física o decisión clara (no emociones)
- Si no hay cambios relevantes, mantener el valor anterior