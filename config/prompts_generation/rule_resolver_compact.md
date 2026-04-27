<!-- variante: compact | rol: rule_resolver (user) | cargado por: build_rule_resolver_prompt() -->
Asignar reglas y escenarios a cada acto.

Anclajes Narrativos (referencia para asignación de reglas):
{anchors_json}

Actos:
{acts_json}

Reglas:
{rules_json}

Escenarios (en orden cronológico):
{scenarios_json}

Instrucciones:
- TODOS los actos deben recibir un scenario_id (usa el order para asignarlos cronológicamente).
- Asigna 0 a 2 reglas por acto según el tipo y la intensidad del acto.
- No repitas la misma regla en múltiples actos salvo motivo dramático claro.
- Compara el content de cada regla con el resonance_anagnorisis (clímax, Acto 3): si coinciden, asígnala solo al Acto 3 o 4.
- El Acto 1 tiene must_not "confirmar lo paranormal" — no le asignes reglas de tipo evento que confirmen el horror.

Respondé ÚNICAMENTE con este JSON (sin texto adicional, sin markdown):
{{"1": {{"rules": [], "scenario_id": "S1"}}, "2": {{"rules": [], "scenario_id": "S2"}}, "3": {{"rules": ["<id>"], "scenario_id": "S3"}}, "4": {{"rules": [], "scenario_id": "S4"}}, "5": {{"rules": [], "scenario_id": "S4"}}}}
