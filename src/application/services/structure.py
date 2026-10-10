"""Estructura del relato (Spec-650): cuántos actos tiene y qué hace cada uno.

La definen las `estructuras` de `config/llm_beats_definition.yaml`; cada historia
elige una (`Story.structure`). Nada del pipeline cuenta los actos con una constante:
pregunta a la estructura de la historia.
"""

from dataclasses import dataclass, field

DEFAULT_STRUCTURE = "largo"


@dataclass(frozen=True)
class Estructura:
    id: str
    label: str
    actos: tuple[dict, ...]  # los actos tal cual el YAML (sin resolver la revelación)
    revela_secreto: int
    palabras_total: str = ""  # para el objetivo del asistente («unas N palabras»)
    hechos_por_acto: str = ""  # lo que pide el Planificador para cada acto
    # D10: {estructura de origen: {acto de allá: acto de acá}} para reubicar las reglas.
    reubicar_desde: dict[str, dict[int, int]] = field(default_factory=dict)

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

    def reubicar(self, number: int, desde: "Estructura") -> int:
        """El acto de esta estructura que equivale al acto `number` de `desde` (D10)."""
        if desde.id == self.id:
            return number
        return self.reubicar_desde[desde.id][number]


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
        if bool(a.get("hechos")) != bool(a.get("hechos_max")):
            raise ValueError(f"{where}, acto {a['id']}: hechos y hechos_max van juntos")
        palabras = a.get("palabras")
        if palabras is not None and not (
            len(palabras) == 2
            and all(isinstance(p, int) for p in palabras)
            and 0 < palabras[0] < palabras[1]
        ):
            raise ValueError(f"{where}, acto {a['id']}: palabras tiene que ser [mínimo, máximo]")
    for key in ("palabras_total", "hechos_por_acto"):  # van a los prompts del asistente
        if not data.get(key):
            raise ValueError(f"{where}: falta {key}")
    revela = data.get("revela_secreto")
    if not isinstance(revela, int) or not 1 <= revela <= len(actos):
        raise ValueError(f"{where}: revela_secreto tiene que ser un acto de la estructura")
    return Estructura(
        id=estructura_id,
        label=data.get("label", ""),
        actos=tuple(actos),
        revela_secreto=revela,
        palabras_total=str(data.get("palabras_total", "")),
        hechos_por_acto=str(data.get("hechos_por_acto", "")),
        reubicar_desde={
            src: {int(k): int(v) for k, v in table.items()}
            for src, table in (data.get("reubicar_desde") or {}).items()
        },
    )


def validate_relocations(structures: dict[str, Estructura]) -> None:
    """D10: de cada estructura a cada otra hay una tabla completa y válida."""
    for target in structures.values():
        for source in structures.values():
            if source.id == target.id:
                continue
            table = target.reubicar_desde.get(source.id)
            where = f"estructura «{target.id}»: reubicar_desde.{source.id}"
            if table is None:
                raise ValueError(f"{where} falta")
            if sorted(table) != source.numeros:
                raise ValueError(f"{where} tiene que traer los actos {source.numeros}")
            if not all(target.tiene(n) for n in table.values()):
                raise ValueError(f"{where} manda a un acto que no existe")
