"""Parser compartido de beats para DirectorUseCase y SynopsisBeatMapper."""

import logging
import re

from src.domain.models import Beat

logger = logging.getLogger(__name__)

# Detecta encabezado de acto: "1." o "1. contenido" o variantes con asteriscos
_SECTION_HEADER = re.compile(r"^\*{0,2}(\d+)\.\*{0,2}\s*(.*)")

# Formatos alternativos que no usan "N." como encabezado
_ALT_PATTERNS: list[re.Pattern] = [
    re.compile(r"^N\.(\d+)\s+(.+)"),               # N.1 Summary
    re.compile(r"^(\d+)\)\s+(.+)"),                 # 1) Summary
    re.compile(r"^[Bb]eat\s+(\d+)[:\-\.]\s*(.+)"), # Beat 1: Summary
    re.compile(r"^Acto\s+(\d+)[^:]*:\s*(.+)"),     # Acto 1 (nombre): Summary
    re.compile(r"^(\d+)\s+(.+)"),                   # 1 Summary (sin separador)
]

# Algunos modelos ponen el header en una línea y el summary en la siguiente
_HEADER_CONTINUATION = re.compile(
    r"^(Acto\s+\d+[^:]*:)\s*\n+\s*(.+)",
    re.MULTILINE,
)

# Prefijos de bullet a limpiar en líneas de contenido
_BULLET_PREFIX = re.compile(r"^[-*•]\s*")


def _normalize_multiline_beats(text: str) -> str:
    """Une encabezados 'Acto N:' solitarios con el texto de la línea siguiente."""
    return _HEADER_CONTINUATION.sub(r"\1 \2", text)


def _parse_grouped(text: str) -> list[Beat]:
    """Parsea formato agrupado: encabezado 'N.' seguido de oraciones con '-'.

    Soporta tanto beats de una línea ('1. contenido') como multi-línea
    ('1.\\n- oración\\n- oración').
    """
    beats: list[Beat] = []
    seen: set[int] = set()
    current_num: int | None = None
    current_lines: list[str] = []

    for raw_line in text.strip().split("\n"):
        line = raw_line.strip()
        m = _SECTION_HEADER.match(line)
        if m:
            if current_num is not None and current_lines and current_num not in seen:
                seen.add(current_num)
                summary = "\n".join(f"- {l}" for l in current_lines) if len(current_lines) > 1 else current_lines[0]
                beats.append(Beat(number=current_num, summary=summary, status="pending"))
            current_num = int(m.group(1))
            current_lines = []
            inline = m.group(2).strip()
            if inline:
                current_lines.append(inline)
        elif current_num is not None and line:
            clean = _BULLET_PREFIX.sub("", line)
            if clean:
                current_lines.append(clean)

    if current_num is not None and current_lines and current_num not in seen:
        seen.add(current_num)
        summary = "\n".join(f"- {l}" for l in current_lines) if len(current_lines) > 1 else current_lines[0]
        beats.append(Beat(number=current_num, summary=summary, status="pending"))

    return beats


def _parse_alt_patterns(text: str) -> list[Beat]:
    """Fallback: parsea línea a línea con patrones alternativos."""
    beats: list[Beat] = []
    seen: set[int] = set()
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        for pattern in _ALT_PATTERNS:
            m = pattern.match(line)
            if m:
                beat_number = int(m.group(1))
                summary = m.group(2).strip()
                if summary and beat_number not in seen:
                    seen.add(beat_number)
                    beats.append(Beat(number=beat_number, summary=summary, status="pending"))
                break
    return beats


def parse_beats(text: str, num_beats: int, story_id=None, caller: str = "PARSER") -> list[Beat]:
    """Parser defensivo compartido. Soporta beats de una línea y multi-línea agrupados."""
    text = _normalize_multiline_beats(text)

    beats = _parse_grouped(text)

    if not beats:
        beats = _parse_alt_patterns(text)

    if not beats:
        logger.warning(
            f"[{caller}] FALLBACK: ningún patrón reconoció la respuesta, "
            f"se usan {num_beats} beats genéricos.\n"
            f"=== RAW RESPONSE ===\n{text}\n=== END RAW ==="
        )
        beats = [
            Beat(number=i, summary=f"Beat #{i} generado automáticamente", status="pending")
            for i in range(1, num_beats + 1)
        ]
    else:
        logger.debug(
            f"[{caller}] {len(beats)} beats parseados OK: "
            f"{[b.summary[:60] for b in beats]}"
        )

    return beats
