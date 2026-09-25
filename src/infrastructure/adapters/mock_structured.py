"""Respuestas JSON del LLM simulado para los roles del asistente (Spec-530).

Coherentes con el esquema que pide cada rol, para que los tests de la API y los
E2E recorran el flujo completo sin un modelo real.
"""


def mock_structured(role: str | None, schema: dict) -> dict:
    if role == "consultor":
        return {"evaluaciones": [_evaluation(i, c) for i, c in enumerate(_criteria(schema))]}
    if role == "planificador":
        return {"actos": [_act(n) for n in range(1, 6)]}
    if role == "verificador":
        return {
            "decisiones_faltantes": [],
            "avisos": [{"acto": 2, "aviso": "El encuentro del acto 2 repite el del acto 1."}],
        }
    return _from_schema(schema, schema)


def _criteria(schema: dict) -> list[str]:
    evaluation = schema.get("$defs", {}).get("EvaluacionCriterio", {})
    return evaluation.get("properties", {}).get("criterio", {}).get("enum", [])


def _evaluation(i: int, criterion: str) -> dict:
    if i == len(_ANSWERS):  # a partir del quinto, cumple
        return {"criterio": criterion, "estado": "cumple", "pregunta": "", "opciones": []}
    return {
        "criterio": criterion,
        "estado": "falta" if i % 2 == 0 else "parcial",
        "pregunta": f"¿Pregunta de ejemplo sobre {criterion}?",
        "opciones": [f"{a} ({criterion})" for a in _ANSWERS],
    }


_ANSWERS = ("Primera opción", "Segunda opción", "Tercera opción", "Cuarta")


def _act(n: int) -> dict:
    return {
        "numero": n,
        "objetivo": f"Objetivo del acto {n}",
        "hechos": [f"Hecho {n}.1 de ejemplo", f"Hecho {n}.2 de ejemplo"],
        "cambio_de": f"Estado al empezar el acto {n}",
        "cambio_a": f"Estado al terminar el acto {n}",
        "escenario": "Escenario de ejemplo",
        "en_escena": [],
        "se_guarda": "" if n == 5 else f"Algo que se revela después del acto {n}",
        "siembra": [],
        "retoma": [],
        "decisiones": [],
    }


def _from_schema(node: dict, root: dict):
    """Instancia mínima de un esquema cualquiera (roles sin respuesta propia)."""
    if "$ref" in node:
        return _from_schema(root["$defs"][node["$ref"].rsplit("/", 1)[-1]], root)
    if "enum" in node:
        return node["enum"][0]
    kind = node.get("type")
    if kind == "object":
        return {k: _from_schema(v, root) for k, v in node.get("properties", {}).items()}
    if kind == "array":
        return []
    if kind in ("integer", "number"):
        return 1
    if kind == "boolean":
        return False
    return "Ejemplo"
