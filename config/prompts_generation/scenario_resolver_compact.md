<!-- variante: compact | rol: scenario_resolver (user) | cargado por: build_scenario_resolver_prompt() -->
Asignar un escenario a cada acto.

Anclajes Narrativos (referencia de progresión dramática):
{anchors_json}

Actos:
{acts_json}

Escenarios (en orden cronológico):
{scenarios_json}

Instrucciones:
- TODOS los actos deben recibir un scenario_id (usa el order para asignarlos cronológicamente).
- Los escenarios se asignan en orden cronológico estricto: S1 al acto 1, S2 al acto 2, etc.
- Si hay más actos que escenarios, el último escenario se repite.

Respondé ÚNICAMENTE con este JSON (sin texto adicional, sin markdown):
{{"1": {{"scenario_id": "S1"}}, "2": {{"scenario_id": "S2"}}, "3": {{"scenario_id": "S3"}}, "4": {{"scenario_id": "S4"}}, "5": {{"scenario_id": "S4"}}}}
