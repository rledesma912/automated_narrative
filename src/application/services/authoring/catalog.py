"""Criterios del taller y opciones de la Dirección (Spec-530), desde `config/`."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_CONFIG = Path(__file__).resolve().parents[4] / "config"


@dataclass(frozen=True)
class Criterion:
    id: str
    nombre: str  # lo que ve el usuario
    pregunta: str  # la pregunta operativa que recibe el Consultor
    por_que: str  # «para qué sirve», para la UI
    acto: int = 0  # Spec-580: en qué acto va la respuesta (0 = no tiene uno fijo)

    def for_story(self, protagonist: str) -> "Criterion":
        """Spec-550 H7: `{protagonista}` → el nombre del protagonista (o «el protagonista»)."""
        name = protagonist.strip() or "el protagonista"

        def fill(text: str) -> str:
            out = text.replace("{protagonista}", name)
            return out.replace(" a el protagonista", " al protagonista").replace(
                " de el protagonista", " del protagonista"
            )

        return Criterion(self.id, fill(self.nombre), self.pregunta, fill(self.por_que), self.acto)


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    detail: str = ""  # `ayuda` o `ejemplo`
    voice: str = ""  # instrucción de estilo para la Voz («cómo lo cuenta»)
    planner: str = ""  # receta del efecto para la escaleta (Spec-560 A5)


@lru_cache
def direction_criteria() -> tuple[Criterion, ...]:
    data = yaml.safe_load((_CONFIG / "workshop_criteria.yaml").read_text(encoding="utf-8"))
    return tuple(
        Criterion(c["id"], c["nombre"], c["pregunta"], c["por_que"], c.get("acto", 0))
        for c in data["direccion"]
    )


def criterion(criterion_id: str) -> Criterion | None:
    return next((c for c in direction_criteria() if c.id == criterion_id), None)


@lru_cache
def _options() -> dict:
    return yaml.safe_load((_CONFIG / "authoring_options.yaml").read_text(encoding="utf-8"))


def effects() -> tuple[Option, ...]:
    return tuple(
        Option(e["id"], e["label"], e.get("ayuda", ""), planner=e.get("planificador", ""))
        for e in _options()["efectos"]
    )


def tellings() -> tuple[Option, ...]:
    return tuple(
        Option(t["id"], t["label"], t.get("ejemplo", ""), t.get("voz", ""))
        for t in _options()["como_lo_cuenta"]
    )


def label_of(options: tuple[Option, ...], option_id: str) -> str:
    return next((o.label for o in options if o.id == option_id), option_id)
