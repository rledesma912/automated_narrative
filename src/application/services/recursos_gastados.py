"""Recursos gastados (Spec-680): lo que ya se vio en muchos relatos.

Viven en `config/recursos_gastados.yaml`: los `hechos` de manual que avisa el
Verificador (A) y los `gestos` que evita la Voz (C2). Se detectan con patrones, no por
raíz (D18). Lo que trae el autor manda (D19): un recurso que aparece en lo suyo no se
evita ni se marca en su historia.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from src.application.services.repetition_check import known_text

_FILE = Path(__file__).resolve().parents[3] / "config" / "recursos_gastados.yaml"


@dataclass(frozen=True)
class Recurso:
    id: str
    nombre: str
    detecta: tuple[re.Pattern, ...]

    def en(self, text: str) -> str | None:
        """El primer tramo de `text` donde aparece, o None."""
        for pattern in self.detecta:
            if m := pattern.search(text or ""):
                return m.group(0)
        return None


@lru_cache
def _load() -> dict[str, tuple[Recurso, ...]]:
    data = yaml.safe_load(_FILE.read_text(encoding="utf-8"))
    out = {}
    for kind in ("hechos", "gestos"):
        ids = [r["id"] for r in data[kind]]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{_FILE.name}: ids repetidos en «{kind}»")
        out[kind] = tuple(
            Recurso(r["id"], r["nombre"], tuple(re.compile(p, re.I) for p in r["detecta"]))
            for r in data[kind]
        )
    return out


def hechos() -> tuple[Recurso, ...]:
    return _load()["hechos"]


def gestos() -> tuple[Recurso, ...]:
    return _load()["gestos"]


def author_text(story) -> str:
    """Lo que escribió el autor, **sin** los actos (D19): los hechos de los actos los
    arma el Planificador, y sus recursos gastados no se perdonan solos."""
    parts = [story.title, story.sinopsis, story.protagonista]
    parts += [p.get("name", "") + " " + p.get("relation", "") for p in story.personajes_full]
    parts += [s.name + " " + s.description for s in story.scenarios]
    parts += [f"{e.name} {e.description} {e.manifestations} {e.limits}" for e in story.entities]
    parts += [r.content for r in story.typed_rules]
    if story.direction:
        d = story.direction
        parts += [d.premise, d.ending, d.form_other]
    parts += [w.answer for w in story.workshop]
    return " ".join(p for p in parts if p)


def sin_los_del_autor(recursos: tuple[Recurso, ...], text: str) -> list[Recurso]:
    return [r for r in recursos if not r.en(text)]


def gestos_a_evitar(story) -> list[Recurso]:
    """Los gestos gastados que la Voz evita en esta historia: sin los que trae el autor,
    contando los actos (si un hecho dice «toma mate», la Voz puede contarlo)."""
    return sin_los_del_autor(gestos(), known_text(story))
