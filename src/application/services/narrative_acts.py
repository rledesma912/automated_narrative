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
