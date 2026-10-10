"""Respuestas JSON del LLM simulado para los roles del asistente (Spec-530).

Coherentes con el esquema que pide cada rol, para que los tests de la API y los
E2E recorran el flujo completo sin un modelo real.
"""

import re


def mock_structured(role: str | None, schema: dict, prompt: str = "") -> dict:
    if role == "consultor":
        return {"evaluaciones": [_evaluation(i, c) for i, c in enumerate(_criteria(schema))]}
    if role == "planificador":
        total = _planned_acts(prompt)
        return {"actos": [_act(n, total) for n in range(1, total + 1)]}
    if role == "verificador":
        return {
            "decisiones": [],
            "avisos": [{"acto": 2, "aviso": "El encuentro del acto 2 repite el del acto 1."}],
        }
    if role == "journal" and "motivos_usados" in schema.get("properties", {}):
        return {
            "hechos": "Pasó lo del acto.",
            "estado": "Sigue en la ruta.",
            "cuerpo": "Un raspón en la mano izquierda.",
            "asi_es": ["toma mate amargo"],
            "motivos_usados": ["un motivo de ejemplo"],
        }
    if role == "guion":
        return _video_script(prompt)
    return _from_schema(schema, schema)


def _video_script(prompt: str) -> dict:
    """Spec-610: un paquete válido para el relato del prompt (lee «ACTO N» y «[n] …»)."""
    acts: dict[int, int] = {}
    current = 0
    for line in prompt.splitlines():
        if m := re.match(r"ACTO (\d+) ", line):
            current = int(m.group(1))
            acts[current] = 0
        elif current and re.match(r"\[(\d+)\] ", line):
            acts[current] += 1
    bloques, momentos = [], []
    # Momentos de a `grupo` párrafos (sin pasar de un acto a otro): entre 10 y 15
    # para un relato largo, uno por párrafo para uno corto.
    grupo = max(1, -(-sum(acts.values()) // 10))
    for acto, total in acts.items():
        for n in range(1, total + 1):
            bloques.append(
                {
                    "acto": acto,
                    "desde": n,
                    "hasta": n,
                    "indicacion": f"Tranquilo, bloque {n} del acto {acto}.",
                    "enfasis": [],
                    "pausa": "larga" if n == total else "corta",
                }
            )
        for desde in range(1, total + 1, grupo):
            momentos.append(
                {
                    "acto": acto,
                    "desde": desde,
                    "hasta": min(desde + grupo - 1, total),
                    "fuerte": acto == 3 and desde == 1,
                    "que_se_ve": f"Un camino de noche (acto {acto})",
                    "lugar": f"camino {acto}",
                    "prompt_imagen": "An empty dirt road at night under a cold moon, 16:9",
                    "prompt_movimiento": "Slow push-in; thin mist drifts across the road.",
                    "transicion": "Corte",
                    "sonido": "Viento entre los árboles",
                }
            )
    return {
        "narra": "hombre",
        "bloques": bloques,
        "momentos": momentos,
        "intro": " ".join(["Bienvenidos otra vez a mi cripta, pónganse cómodos."] * 8),
        "outro": " ".join(["Conozco a algunos de ustedes y no me quedaría ahí."] * 11)
        + " Buenas noches.",
    }


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


def _planned_acts(prompt: str) -> int:
    """Spec-650: tantos actos como lista el prompt del Planificador («N. Nombre (intensidad
    …)»); sin prompt, los de la estructura larga."""
    listed = re.findall(r"^(\d+)\. .+\(intensidad ", prompt, re.M)
    if listed:
        return max(int(n) for n in listed)
    from src.application.services.beat_spec_repository import BeatSpecRepository

    return BeatSpecRepository().estructura().num_actos


def _act(n: int, total: int) -> dict:
    return {
        "numero": n,
        "como_llega": "" if n == 1 else f"Esa misma noche, después del acto {n - 1}, sigue",
        "objetivo": f"Objetivo del acto {n}",
        "hechos": [f"Hecho {n}.1 de ejemplo", f"Hecho {n}.2 de ejemplo"],
        "cambio_de": f"Estado al empezar el acto {n}",
        "cambio_a": f"Estado al terminar el acto {n}",
        "escenario": "Escenario de ejemplo",
        "en_escena": [],
        "se_guarda": "" if n == total else f"Algo que se revela después del acto {n}",
        "se_revela_en": 0 if n == total else n + 1,
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
