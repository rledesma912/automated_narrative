<!-- variante: compact | rol: rule_resolver (user) | cargado por: build_rule_resolver_prompt() -->
## INFORMACIÓN DE LA HISTORIA 

SINOPSIS:
{sinopsis}

PROTAGONISTAS:
{protagonistas}

REGLAS DEL USUARIO:
{reglas}

ESCENARIOS DETALLADOS:
{escenarios}

## ACTOS NARRATIVOS (ESTRUCTURA OBLIGATORIA):

1. EXPOSICIÓN:
   - Establece la normalidad inicial de la historia.
   - Introduce reglas base del mundo.
   - Primera fisura o anomalía leve que sea cliffhanger para el siguiente acto.

2. ACCIÓN_ASCENDENTE:
   - Inicia con una normalidad aparente antes del conflicto.
   - Activa el conflicto mediante una transgresión o evento disruptivo.
   - Aumenta la tensión progresivamente.

3. CLÍMAX:
   - Momento de máxima intensidad.
   - Obliga al protagonista a reconocer el horror o la verdad.
   - Las reglas más críticas deben estar presentes aquí.

4. ACCIÓN_DESCENDENTE:
   - Consecuencias del clímax.
   - El protagonista entra en colapso, huida o reacción desesperada.
   - El mundo puede volverse hostil o distorsionado.

5. DESENLACE:
   - Puede haber escape parcial o resolución incompleta.
   - Debe sugerir secuelas o persistencia del horror.
   - Cierre de la historia.

---

TAREA:
Analiza la historia identificando los actos narrativos y asigna a cada acto:

1. Las reglas de usuario se asocian considerando su función narrativa.
2. Cada acto podría tener más de una regla.
3. El listado de escenarios es cronológico a cada acto.

---

REGLAS DE ASIGNACIÓN:

- Las reglas deben aparecer cuando son dramáticamente relevantes, no antes.

---

RESPONDE ÚNICAMENTE CON ESTE JSON:
{{
  "ACT 1": {{ "rules": [...], "scenario": "..." }},
  "ACT 2": {{ "rules": [...], "scenario": "..." }},
  "ACT 3": {{ "rules": [...], "scenario": "..." }},
  "ACT 4": {{ "rules": [...], "scenario": "..." }},
  "ACT 5": {{ "rules": [...], "scenario": "..." }}
}}