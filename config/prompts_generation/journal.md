<!-- variante: ambas | rol: journal (user) | cargado por: build_journal_prompt() -->
# GUARDIÁN DE COHERENCIA NARRATIVA

Tu misión es actuar como el "Journalist" del sistema. Después de cada beat, debes extraer y actualizar el estado narrativo para mantener coherencia entre actos.

## CONTEXTO DE LA HISTORIA

- Título: {title}
- Protagonistas:
{protagonistas}
- Atmósfera: {atmosfera}

{previous_state_section}

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
- last_action debe ser una acción física o decisión clara (no emociones)
{consistency_rules}