"""El paquete frente al relato corregido (Spec-610 §7.2, T3.1).

- `al_dia`: el relato es el mismo con el que se armó.
- `cambio_el_texto`: cambió el texto pero cada acto tiene los mismos párrafos: el
  paquete sigue andando (bloques y momentos leen el texto actual), con un aviso.
- `cambiaron_parrafos`: algún acto tiene otra cantidad de párrafos: sus bloques y
  momentos ya no apuntan a lo mismo; los PDF no se bajan hasta rearmar.

Las marcas de remarcado se reubican por su texto (los mismos casos que `marcas.js`).
"""

from dataclasses import dataclass, field
from typing import Literal

from src.application.services import narrative_acts
from src.application.services.video.script_builder import _key, narrative_hash
from src.domain.video import Mark, VideoScript

Estado = Literal["al_dia", "cambio_el_texto", "cambiaron_parrafos"]


@dataclass
class ScriptState:
    estado: Estado
    actos: list[int] = field(default_factory=list)  # los que cambiaron de párrafos

    def as_dict(self) -> dict:
        return {"estado": self.estado, "actos": self.actos}


def state(script: VideoScript, content: str) -> ScriptState:
    if narrative_hash(content) == script.narrative_hash:
        return ScriptState("al_dia")
    acts = narrative_acts.split(content)
    now = {n: len(acts.paragraphs(n)) for n in acts.numbers()}
    changed = sorted(
        n
        for n in set(now) | set(script.parrafos_por_acto)
        if now.get(n) != script.parrafos_por_acto.get(n)
    )
    return ScriptState("cambiaron_parrafos", changed) if changed else ScriptState("cambio_el_texto")


def _matches(tokens: list[str], start: int, wanted: list[str]) -> bool:
    keys = [_key(t) for t in tokens[start : start + len(wanted)]]
    return len(keys) == len(wanted) and keys == wanted


def relocate(tokens: list[str], marks: list[Mark]) -> tuple[list[Mark], list[str]]:
    """Las marcas que siguen (en su lugar o reubicadas) y los textos de las que se pierden."""
    kept: list[Mark] = []
    lost: list[str] = []
    taken: set[int] = set()
    pending: list[Mark] = []
    for m in marks:  # primero las que siguen en su lugar
        wanted = [_key(w) for w in m.texto.split() if _key(w)]
        span = range(m.desde_palabra, m.desde_palabra + len(wanted))
        if wanted and _matches(tokens, m.desde_palabra, wanted) and not taken.intersection(span):
            kept.append(m.model_copy(update={"hasta_palabra": span[-1]}))
            taken.update(span)
        else:
            pending.append(m)
    for m in pending:  # después, las que hay que buscar
        wanted = [_key(w) for w in m.texto.split() if _key(w)]
        start = next(
            (
                i
                for i in range(len(tokens) - len(wanted) + 1)
                if wanted
                and _matches(tokens, i, wanted)
                and not taken.intersection(range(i, i + len(wanted)))
            ),
            None,
        )
        if start is None:
            lost.append(m.texto)
            continue
        end = start + len(wanted) - 1
        kept.append(
            Mark(desde_palabra=start, hasta_palabra=end, texto=" ".join(tokens[start : end + 1]))
        )
        taken.update(range(start, end + 1))
    return sorted(kept, key=lambda m: m.desde_palabra), lost


def block_tokens(
    content_acts: narrative_acts.NarrativeActs, acto: int, desde: int, hasta: int
) -> list[str]:
    if acto not in content_acts.acts:
        return []
    paragraphs = content_acts.paragraphs(acto)[desde - 1 : hasta]
    return [w for p in paragraphs for w in p.split()]
