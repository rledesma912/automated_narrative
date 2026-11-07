"""Los actos de un relato guardado (Spec-610 T1.1).

`generated_narrative.content` es Markdown: un preámbulo opcional y un `## Acto N` por
acto, con los párrafos separados por una línea en blanco (lo arma
`GenerateNarrativesUseCase._consolidate_content`). Acá se parte en actos y párrafos y
se vuelve a unir, para corregir un acto sin tocar los demás.
"""

import re
from dataclasses import dataclass, field

_ACT_HEADER = re.compile(r"^## Acto (\d+)[ \t]*$", re.M)
_BLANK_LINES = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)*")


@dataclass
class NarrativeActs:
    """Un relato partido: el preámbulo y el texto de cada acto, en orden."""

    preamble: str = ""
    acts: dict[int, str] = field(default_factory=dict)
    # Spec-750: el largo de la versión ("" = se deduce de cuántos actos tiene).
    structure: str = ""

    def numbers(self) -> list[int]:
        return list(self.acts)

    def paragraphs(self, number: int) -> list[str]:
        return paragraphs(self.acts[number])


def normalize(text: str) -> str:
    """Saltos de línea de Unix, sin espacios al final de cada línea y una sola línea
    en blanco entre párrafos."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return _BLANK_LINES.sub("\n\n", text).strip()


def paragraphs(text: str) -> list[str]:
    """Los párrafos de un texto (separados por al menos una línea en blanco)."""
    return [p for p in normalize(text).split("\n\n") if p]


def split(content: str) -> NarrativeActs:
    """Parte el contenido de un relato en preámbulo y actos."""
    matches = list(_ACT_HEADER.finditer(content))
    if not matches:
        return NarrativeActs(preamble=content.strip())
    acts: dict[int, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        acts[int(match.group(1))] = content[match.end() : end].strip()
    return NarrativeActs(preamble=content[: matches[0].start()].strip(), acts=acts)


def join(narrative: NarrativeActs) -> str:
    """Vuelve a armar el contenido, con el mismo formato que la consolidación."""
    parts = [narrative.preamble] if narrative.preamble else []
    parts += [f"## Acto {number}\n\n{text}" for number, text in narrative.acts.items()]
    return "\n\n".join(parts)


def replace_act(content: str, number: int, text: str) -> str:
    """El contenido con el acto `number` reemplazado por `text` (normalizado).

    Raises:
        KeyError: el relato no tiene ese acto.
    """
    narrative = split(content)
    if number not in narrative.acts:
        raise KeyError(number)
    narrative.acts[number] = normalize(text)
    return join(narrative)


def structure_by_count(cantidad: int) -> str:
    """El largo de una versión sin el dato (anterior a la Spec-750), por cuántos actos tiene.

    Hasta la Spec-750 no había larga: 5 actos es la media. Una cantidad rara se toma como
    la de siempre.
    """
    from src.application.services.beat_spec_repository import BeatSpecRepository
    from src.application.services.structure import DEFAULT_STRUCTURE

    repo = BeatSpecRepository()
    found = [sid for sid in repo.structure_ids if repo.estructura(sid).num_actos == cantidad]
    return DEFAULT_STRUCTURE if DEFAULT_STRUCTURE in found or not found else found[0]


def structure_of(narrative) -> str:
    """Spec-750: el largo de una versión guardada (`GeneratedNarrative`)."""
    return narrative.structure or structure_by_count(len(split(narrative.content).numbers()))


def split_narrative(narrative) -> NarrativeActs:
    """Los actos de una versión guardada, con su largo."""
    acts = split(narrative.content)
    acts.structure = structure_of(narrative)
    return acts


def structure_of_acts(acts: NarrativeActs) -> str:
    """El largo de un relato partido: el suyo o, si no lo trae, por cuántos actos tiene."""
    return acts.structure or structure_by_count(len(acts.numbers()))


def same_structure(story, narrative) -> bool:
    """Spec-650 D11: la versión se escribió con el largo actual de la historia (si la
    historia cambió de largo, sus versiones viejas no se regeneran). Spec-750: la media y
    la larga tienen los mismos actos: cuenta el largo guardado, no solo los actos."""
    from src.application.services.beat_spec_repository import BeatSpecRepository

    expected = BeatSpecRepository().estructura(story.structure).numeros
    return (
        structure_of(narrative) == story.structure
        and split(narrative.content).numbers() == expected
    )
