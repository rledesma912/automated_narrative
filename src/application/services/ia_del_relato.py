"""Qué IA escribió cada versión del relato (Spec-740 C1–C4).

Sale del registro (`llm_call`): por acto vale la **última** llamada de la Voz de ese relato
(regenerar un acto reemplaza su dato, B5). El resto del trabajo (preguntas, actos, memoria,
guion) va aparte, con el último modelo de cada tarea. Sin registro, no se dice nada (B6).
"""

from functools import cache
from pathlib import Path

import yaml

from src.domain.llm_context import LLMCall

_CONFIG = Path("config/modelos_ia.yaml")


@cache
def _config() -> dict:
    return yaml.safe_load(_CONFIG.read_text(encoding="utf-8")) or {}


def nombre_del_modelo(model: str | None) -> str:
    """El nombre para mostrar; sin entrada en la config, el id sin plataforma ni `:free`."""
    model = model or ""
    for entry in _config().get("modelos", []):
        if entry["contiene"] in model:
            return entry["nombre"]
    return model.rsplit("/", 1)[-1].removesuffix(":free") or "?"


def resumen(del_relato: list[LLMCall], de_la_historia: list[LLMCall]) -> dict:
    """`modelos`: cada modelo de la Voz con sus actos, en orden; `por_acto`: el de cada acto;
    `resto`: el último modelo de cada tarea (del relato y del asistente de la historia)."""
    por_acto: dict[int, str] = {}
    for call in del_relato:  # ordenadas: gana la última de cada acto
        if call.role == "voz" and call.act is not None:
            por_acto[call.act] = nombre_del_modelo(call.model)

    modelos: list[dict] = []
    for act in sorted(por_acto):
        nombre = por_acto[act]
        grupo = next((m for m in modelos if m["nombre"] == nombre), None)
        if grupo is None:
            modelos.append({"nombre": nombre, "actos": [act]})
        else:
            grupo["actos"].append(act)

    tareas = _config().get("tareas", {})
    ultimo: dict[str, str] = {}
    for call in [*de_la_historia, *del_relato]:
        if call.role in tareas:
            ultimo[call.role] = nombre_del_modelo(call.model)
    resto = [{"tarea": tareas[r], "nombre": ultimo[r]} for r in tareas if r in ultimo]

    return {
        "modelos": modelos,
        "por_acto": {str(a): n for a, n in sorted(por_acto.items())},
        "resto": resto if modelos else [],
    }
