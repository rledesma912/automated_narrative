"""Estructura del relato (Spec-650): cuántos actos tiene y qué hace cada uno.

La definen las `estructuras` de `config/llm_beats_definition.yaml`; cada historia
elige una (`Story.structure`). Nada del pipeline cuenta los actos con una constante:
pregunta a la estructura de la historia.
"""

from dataclasses import dataclass

DEFAULT_STRUCTURE = "largo"


@dataclass(frozen=True)
class Estructura:
    id: str
    label: str
    actos: tuple[dict, ...]  # los actos tal cual el YAML (sin resolver la revelación)
    revela_secreto: int

    @property
    def num_actos(self) -> int:
        return len(self.actos)

    @property
    def numeros(self) -> list[int]:
        return [a["id"] for a in self.actos]

    @property
    def ultimo(self) -> int:
        """El acto final: el del desenlace y el del final que decidió el autor."""
        return self.actos[-1]["id"]

    def tiene(self, number: int) -> bool:
        return 1 <= number <= self.num_actos

    def acto(self, number: int) -> dict:
        """El acto `number` (sin resolver); `{}` si la estructura no lo tiene."""
        return next((a for a in self.actos if a["id"] == number), {})


def validate(estructura_id: str, data: dict, exposures: dict) -> Estructura:
    """Arma la estructura y falla al cargar si el YAML está incompleto (no en medio de un job)."""
    actos = data.get("actos") or []
    where = f"estructura «{estructura_id}»"
    if [a.get("id") for a in actos] != list(range(1, len(actos) + 1)) or not actos:
        raise ValueError(f"{where}: los actos tienen que ser 1..N en orden")
    for a in actos:
        missing = [k for k in ("label", "nombre_ui", "intent", "intensity") if not a.get(k)]
        if missing:
            raise ValueError(f"{where}, acto {a['id']}: falta {', '.join(missing)}")
        unknown = [v for v in (a.get("entity_exposure") or {}).values() if v not in exposures]
        if unknown:
            raise ValueError(f"{where}, acto {a['id']}: exposición desconocida {unknown}")
    revela = data.get("revela_secreto")
    if not isinstance(revela, int) or not 1 <= revela <= len(actos):
        raise ValueError(f"{where}: revela_secreto tiene que ser un acto de la estructura")
    return Estructura(
        id=estructura_id,
        label=data.get("label", ""),
        actos=tuple(actos),
        revela_secreto=revela,
    )
