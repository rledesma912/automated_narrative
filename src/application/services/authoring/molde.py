"""Molde de la historia (Spec-670): base + forma + giro + largo, desde `config/moldes/`.

El molde decide qué se pregunta (criterios), qué pide cada acto (intenciones) y qué
reglas sigue el Planificador. Todo lo que lee el taller pasa por `Molde.criterios`
(D11): las respuestas de criterios que el molde no tiene (p. ej. de una forma
anterior) no llegan a ningún prompt.

Una historia sin forma (vieja, importada) usa la primera forma del catálogo, la de
siempre; una forma o un giro que ya no existe cae ahí también (D16).
"""

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from src.application.services.authoring import catalog
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.structure import DEFAULT_STRUCTURE
from src.domain.models import Story

logger = logging.getLogger(__name__)

_DIR = Path(__file__).resolve().parents[4] / "config" / "moldes"
MAX_CRITERIOS_FORMA = 4  # D10: base (5) + forma (≤ 4) = 9 como hoy; el giro suma 1
MAX_CRITERIOS_GIRO = 1


@dataclass(frozen=True)
class Revela:
    criterio: str  # el criterio cuya respuesta se revela
    texto: str  # lo que se suma a la intención del acto donde se revela
    acto: dict[str, int] = field(default_factory=dict)  # {estructura: n}; sin eso, `revela_secreto`


@dataclass(frozen=True)
class Forma:
    id: str
    nombre: str
    ayuda: str
    arco: str  # D1: cómo es la forma, para la IA que la sugiere
    criterios: tuple[str, ...]
    actos: dict[str, dict[int, str]] = field(default_factory=dict)  # {estructura: {n: intención}}
    reglas: tuple[str, ...] = ()
    revela: Revela | None = None
    arco_del_autor: bool = False  # D14: «Otra»


@dataclass(frozen=True)
class Giro:
    id: str
    nombre: str
    ayuda: str
    criterios: tuple[str, ...]
    reglas: tuple[str, ...] = ()
    no_con: tuple[str, ...] = ()  # formas que ya preguntan lo mismo: con ellas no va


@dataclass(frozen=True)
class Catalogo:
    base: tuple[str, ...]
    formas: tuple[Forma, ...]
    giros: tuple[Giro, ...]

    @property
    def por_defecto(self) -> Forma:
        return self.formas[0]

    def forma(self, forma_id: str) -> Forma | None:
        return next((f for f in self.formas if f.id == forma_id), None)

    def giro(self, giro_id: str) -> Giro | None:
        return next((g for g in self.giros if g.id == giro_id), None)

    def giros_para(self, forma_id: str) -> tuple[Giro, ...]:
        """Los giros que se pueden sumar a la forma (los de `no_con` no)."""
        return tuple(g for g in self.giros if forma_id not in g.no_con)


@dataclass(frozen=True)
class Molde:
    forma: Forma
    giro: Giro | None
    structure: str
    arco: str = ""  # D14: cómo contó el autor su historia («Otra»)

    @property
    def ids(self) -> tuple[str, ...]:
        """Los criterios del molde, en el orden del banco (el de los actos)."""
        wanted = {
            *catalogo().base,
            *self.forma.criterios,
            *(self.giro.criterios if self.giro else ()),
        }
        return tuple(c.id for c in catalog.criteria_bank() if c.id in wanted)

    @property
    def criterios(self) -> tuple[catalog.Criterion, ...]:
        wanted = set(self.ids)
        return tuple(c for c in catalog.criteria_bank(self.structure) if c.id in wanted)

    def intencion(self, number: int, default: str) -> str:
        """Lo que pide el acto `number`: el de la forma o, si no trae, el de la estructura."""
        return self.forma.actos.get(self.structure, {}).get(number) or default

    @property
    def reglas(self) -> tuple[str, ...]:
        return (*self.forma.reglas, *(self.giro.reglas if self.giro else ()))

    @property
    def revela(self) -> Revela | None:
        return self.forma.revela

    def acto_revela(self, revela_secreto: int) -> int:
        """El acto donde se revela: el de la forma o, si no dice, el de la estructura."""
        return (self.revela.acto.get(self.structure) if self.revela else None) or revela_secreto


def for_story(story: Story) -> Molde:
    d = story.direction
    cat = catalogo()
    forma_id = d.form if d and d.form else cat.por_defecto.id
    forma = cat.forma(forma_id)
    if forma is None:
        logger.warning(
            "Forma desconocida «%s» en la historia %s: uso la de siempre", forma_id, story.id
        )
        forma = cat.por_defecto
    giro = None
    if d and d.ingredient:
        giro = cat.giro(d.ingredient)
        if giro is None:
            logger.warning(
                "Giro desconocido «%s» en la historia %s: sin giro", d.ingredient, story.id
            )
        elif forma.id in giro.no_con:
            logger.warning(
                "El giro «%s» no va con «%s» (historia %s): sin giro", giro.id, forma.id, story.id
            )
            giro = None
    arco = d.form_other.strip() if d and forma.arco_del_autor else ""
    return Molde(forma, giro, story.structure or DEFAULT_STRUCTURE, arco)


def default(structure: str = DEFAULT_STRUCTURE) -> Molde:
    """El molde de siempre: la primera forma, sin giro."""
    return Molde(catalogo().por_defecto, None, structure)


@lru_cache
def catalogo() -> Catalogo:
    """Carga y valida `config/moldes/` (falla al arrancar, no en medio de un job)."""
    formas_yaml = yaml.safe_load((_DIR / "formas.yaml").read_text(encoding="utf-8"))
    giros_yaml = yaml.safe_load((_DIR / "ingredientes.yaml").read_text(encoding="utf-8"))
    banco = {c.id for c in catalog.criteria_bank()}
    estructuras = BeatSpecRepository()

    def criterios(where: str, ids, tope: int | None) -> tuple[str, ...]:
        ids = tuple(ids or ())
        unknown = [i for i in ids if i not in banco]
        if unknown:
            raise ValueError(
                f"{where}: criterios que no están en workshop_criteria.yaml: {unknown}"
            )
        if tope is not None and len(ids) > tope:
            raise ValueError(f"{where}: {len(ids)} criterios (máximo {tope}, D10)")
        return ids

    def texto(where: str, data: dict, key: str) -> str:
        value = str(data.get(key) or "").strip()
        if not value:
            raise ValueError(f"{where}: falta «{key}»")
        return value

    base = criterios("formas.yaml, base", formas_yaml.get("base"), None)
    formas = []
    for f in formas_yaml.get("formas") or []:
        where = f"formas.yaml, forma «{f.get('id')}»"
        actos: dict[str, dict[int, str]] = {}
        for sid, por_acto in (f.get("actos") or {}).items():
            numeros = estructuras.estructura(sid).numeros
            if sorted(por_acto) != numeros:
                raise ValueError(f"{where}: los actos de «{sid}» tienen que ser {numeros}")
            actos[sid] = {int(n): str(v).strip() for n, v in por_acto.items()}
        if actos and set(actos) != set(estructuras.structure_ids):
            raise ValueError(
                f"{where}: faltan los actos de {set(estructuras.structure_ids) - set(actos)}"
            )
        ids = criterios(where, f.get("criterios"), MAX_CRITERIOS_FORMA)
        revela = None
        if f.get("revela"):
            r = f["revela"]
            if r.get("criterio") not in ids:
                raise ValueError(f"{where}: «revela» usa un criterio que la forma no tiene")
            acto = {str(k): int(v) for k, v in (r.get("acto") or {}).items()}
            for sid, n in acto.items():
                if n not in estructuras.estructura(sid).numeros:
                    raise ValueError(f"{where}: «revela.acto» {n} no existe en «{sid}»")
            if acto and set(acto) != set(estructuras.structure_ids):
                raise ValueError(f"{where}: «revela.acto» tiene que decir el acto de cada largo")
            revela = Revela(r["criterio"], texto(where, r, "texto"), acto)
        formas.append(
            Forma(
                id=texto(where, f, "id"),
                nombre=texto(where, f, "nombre"),
                ayuda=texto(where, f, "ayuda"),
                arco=texto(where, f, "arco"),
                criterios=ids,
                actos=actos,
                reglas=tuple(str(x).strip() for x in f.get("reglas") or ()),
                revela=revela,
                arco_del_autor=bool(f.get("arco_del_autor")),
            )
        )
    giros = []
    for g in giros_yaml.get("ingredientes") or []:
        where = f"ingredientes.yaml, giro «{g.get('id')}»"
        giros.append(
            Giro(
                id=texto(where, g, "id"),
                nombre=texto(where, g, "nombre"),
                ayuda=texto(where, g, "ayuda"),
                criterios=criterios(where, g.get("criterios"), MAX_CRITERIOS_GIRO),
                reglas=tuple(str(x).strip() for x in g.get("reglas") or ()),
                no_con=tuple(g.get("no_con") or ()),
            )
        )
    if not formas:
        raise ValueError("formas.yaml: no hay formas")
    if formas[0].actos or formas[0].reglas:
        raise ValueError(
            "formas.yaml: la primera forma es la de siempre (sin actos ni reglas propias)"
        )
    ids = [f.id for f in formas] + [g.id for g in giros]
    if len(ids) != len(set(ids)):
        raise ValueError("config/moldes: ids repetidos")
    formas_ids = {f.id for f in formas}
    for g in giros:
        if set(g.no_con) - formas_ids:
            raise ValueError(
                f"ingredientes.yaml, giro «{g.id}»: «no_con» con formas que no existen"
            )
    return Catalogo(base, tuple(formas), tuple(giros))
