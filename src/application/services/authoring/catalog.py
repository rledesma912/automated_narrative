"""Criterios del taller y opciones de la Dirección (Spec-530), desde `config/`."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from src.application.services.structure import DEFAULT_STRUCTURE

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
def criteria_bank(structure: str = DEFAULT_STRUCTURE) -> tuple[Criterion, ...]:
    """Spec-670: todos los criterios (el banco), con su `acto` en la estructura pedida
    (Spec-650). Cuáles pregunta cada historia lo dice su molde (`molde.py`)."""
    data = yaml.safe_load((_CONFIG / "workshop_criteria.yaml").read_text(encoding="utf-8"))
    return tuple(
        Criterion(
            c["id"], c["nombre"], c["pregunta"], c["por_que"], _for(c.get("acto", 0), structure)
        )
        for c in data["direccion"]
    )


def direction_criteria(structure: str = DEFAULT_STRUCTURE) -> tuple[Criterion, ...]:
    """Los criterios del molde de siempre (la primera forma, sin giro). Para lo que no
    tiene una historia a mano (`/options`); lo de cada historia es `molde.for_story`."""
    from src.application.services.authoring import molde  # molde importa este módulo

    return molde.default(structure).criterios


def criterion(criterion_id: str, structure: str = DEFAULT_STRUCTURE) -> Criterion | None:
    """Un criterio del banco (de cualquier forma o giro)."""
    return next((c for c in criteria_bank(structure) if c.id == criterion_id), None)


def _for(value, structure: str):
    """Spec-650: un valor del YAML que puede venir por estructura (`{largo: …, corto: …}`)."""
    if isinstance(value, dict):
        if structure not in value:
            raise KeyError(f"falta la variante «{structure}» en {value}")
        return value[structure]
    return value


@lru_cache
def _options() -> dict:
    return yaml.safe_load((_CONFIG / "authoring_options.yaml").read_text(encoding="utf-8"))


def effects(structure: str = DEFAULT_STRUCTURE) -> tuple[Option, ...]:
    """Spec-650: la receta del efecto (`planificador`) de la estructura pedida."""
    return tuple(
        Option(
            e["id"],
            e["label"],
            e.get("ayuda", ""),
            planner=_for(e.get("planificador", ""), structure),
        )
        for e in _options()["efectos"]
    )


def tellings() -> tuple[Option, ...]:
    return tuple(
        Option(t["id"], t["label"], t.get("ejemplo", ""), t.get("voz", ""))
        for t in _options()["como_lo_cuenta"]
    )


@dataclass(frozen=True)
class Habla:
    """Spec-680 C1: cómo habla quien narra."""

    id: str
    label: str
    ayuda: str  # para la UI
    prompt: str  # «español rioplatense»: lo que dicen la Voz, la Memoria y el Planificador
    voz: str  # una línea más para la Voz (vacía en la de siempre)
    ajenas: tuple[str, ...]  # patrones de palabras que no van en esta habla


@lru_cache
def hablas() -> tuple[Habla, ...]:
    """La primera es la de siempre. Los patrones de `ajenas` se validan al cargar."""
    out = []
    for h in _options()["hablas"]:
        patterns = tuple(h.get("ajenas") or ())
        for pattern in patterns:
            re.compile(pattern)  # un patrón roto falla al arrancar, no en un relato
        out.append(Habla(h["id"], h["label"], h["ayuda"], h["prompt"], h["voz"], patterns))
    return tuple(out)


def habla(habla_id: str) -> Habla | None:
    return next((h for h in hablas() if h.id == habla_id), None)


def habla_de(story) -> Habla:
    """La de la historia; sin habla, o con una que ya no existe, la de siempre."""
    chosen = story.direction.habla if story.direction else ""
    return habla(chosen) or hablas()[0]


def label_of(options: tuple[Option, ...], option_id: str) -> str:
    return next((o.label for o in options if o.id == option_id), option_id)
