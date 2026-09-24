"""Formateo de un relato para el TTS (Spec-490 §2.1).

Convierte el `content` consolidado de un `GeneratedNarrative` (`## Acto N` +
prosa) en el `.md` que consume `audiogen`: título, rótulos de acto, un párrafo
por línea y `[pause=…]` entre actos. `audiogen` saltea en silencio las líneas
que empiezan con `#`, `-`, `*` o `>`, así que ninguna línea de prosa puede
quedar así. Determinístico, sin LLM.
"""

import re
import unicodedata
from datetime import datetime

from src.utils import ARGENTINA_TZ

PAUSE_BETWEEN_ACTS_MS = 1500
SLUG_MAX_LENGTH = 60
DEFAULT_SLUG = "relato"

_ACT_HEADING = re.compile(r"^##\s+(?:Acto|Beat)\s+(\d+)\s*$", re.MULTILINE | re.IGNORECASE)
_BLANK_LINES = re.compile(r"\n\s*\n")
_SEPARATOR = re.compile(r"^(?:[-*_]\s*){3,}$")
_LEADING_QUOTE_OR_HEADING = re.compile(r"^[>#\s]+")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"\*(?!\s)(.+?)(?<!\s)\*")
_UNDERSCORE = re.compile(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)")
_DIALOGUE_DASH = re.compile(r"^[-–]+\s*")
_STARTS_DIALOGUE = re.compile(r"^[-–—]")
_BRACKETED = re.compile(r"^\[(.*)\]$")
_SKIPPED_BY_TTS = "#-*>"


def split_acts(content: str) -> list[tuple[int | None, str]]:
    """Parte el relato en `(número de acto, prosa)`.

    El texto previo al primer encabezado vuelve como preámbulo con número
    `None`; los tramos sin prosa se omiten.
    """
    content = (content or "").replace("\r\n", "\n")
    pieces = _ACT_HEADING.split(content)
    acts: list[tuple[int | None, str]] = []
    if pieces[0].strip():
        acts.append((None, pieces[0].strip()))
    for i in range(1, len(pieces), 2):
        prose = pieces[i + 1].strip()
        if prose:
            acts.append((int(pieces[i]), prose))
    return acts


def clean_prose(text: str) -> list[str]:
    """Párrafos de prosa, uno por elemento, en una forma que el TTS no saltea."""
    paragraphs: list[str] = []
    for block in _BLANK_LINES.split((text or "").replace("\r\n", "\n")):
        current: list[str] = []
        for raw in block.split("\n"):
            line = raw.strip()
            if not line:
                continue
            # Un diálogo en su propia línea es su propio párrafo.
            if current and _STARTS_DIALOGUE.match(line):
                paragraphs.append(" ".join(current))
                current = []
            current.append(line)
        if current:
            paragraphs.append(" ".join(current))
    return [cleaned for p in paragraphs if (cleaned := _clean_paragraph(p))]


def _clean_paragraph(paragraph: str) -> str:
    if _SEPARATOR.match(paragraph):
        return ""
    line = _LEADING_QUOTE_OR_HEADING.sub("", paragraph)
    line = _BOLD.sub(r"\1", line)
    line = _ITALIC.sub(r"\1", line)
    line = _UNDERSCORE.sub(r"\1", line)
    line = line.lstrip("*").lstrip()
    line = _DIALOGUE_DASH.sub("—", line)
    bracketed = _BRACKETED.match(line)
    if bracketed:
        line = bracketed.group(1).strip()
    # Red de seguridad: lo que quede con un inicio que el TTS saltearía.
    return line.lstrip(_SKIPPED_BY_TTS + " ")


def to_tts_markdown(title: str, content: str) -> str:
    """El `.md` completo para `audiogen`."""
    lines = [f"# {' '.join((title or '').split())}"]
    first_act = True
    for number, prose in split_acts(content):
        paragraphs = clean_prose(prose)
        if not paragraphs:
            continue
        if number is not None:
            if not first_act:
                lines.append(f"[pause={PAUSE_BETWEEN_ACTS_MS}]")
            lines.append(f"## Acto {number}")
            first_act = False
        lines.extend(paragraphs)
    return "\n\n".join(lines) + "\n"


def export_filename(title: str, created_at: datetime) -> str:
    """`<slug>-AAAA-MM-DD-HHMM.md`, con la hora en zona argentina."""
    if created_at.tzinfo is not None:
        created_at = created_at.astimezone(ARGENTINA_TZ)
    return f"{_slugify(title)}-{created_at:%Y-%m-%d-%H%M}.md"


def _slugify(title: str) -> str:
    ascii_title = (
        unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    slug = slug[:SLUG_MAX_LENGTH].rstrip("-")
    return slug or DEFAULT_SLUG
