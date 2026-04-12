---
MEMORY
Extraer el estado narrativo ACTUAL en formato estructurado.

Debes generar EXACTAMENTE este objeto:

{{
  "location": "...",
  "characters": "...",
  "situation": "...",
  "active_threat": "...",
  "goal": "...",
  "last_action": "..."
}}

DEFINICIONES:

- location: lugar físico actual donde ocurre la escena
- characters: personajes presentes en la escena (solo nombres)
- situation: qué está ocurriendo en este momento
- active_threat: peligro inmediato o elemento perturbador activo
- goal: objetivo inmediato del protagonista
- last_action: última acción concreta realizada por el protagonista justo antes de terminar el capítulo

REGLAS:
- No inventar información
- last_action debe ser una acción física o decisión clara (no emociones)
- Debe representar el último momento narrativo del capítulo

---

CAPÍTULO A ANALIZAR:

{{chapter_text}}

---