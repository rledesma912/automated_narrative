"""Parser compartido de beats para DirectorUseCase y SynopsisBeatMapper."""

import logging
import re

from src.domain.models import Beat

logger = logging.getLogger(__name__)

# Patrones en orden de especificidad. Se prueban en secuencia; el primero que
# matchea gana. Cubren los formatos reales observados en distintos modelos.
_BEAT_PATTERNS: list[re.Pattern] = [
    re.compile(r"^N\.(\d+)\s+(.+)"),                       # N.1 Summary
    re.compile(r"^\*{0,2}(\d+)\.\*{0,2}\s+(.+)"),         # 1. / **1.** Summary
    re.compile(r"^(\d+)\)\s+(.+)"),                        # 1) Summary
    re.compile(r"^[Bb]eat\s+(\d+)[:\-\.]\s*(.+)"),        # Beat 1: / beat 1- Summary
    re.compile(r"^Acto\s+(\d+)[^:]*:\s*(.+)"),            # Acto 1 (nombre): Summary
    re.compile(r"^(\d+)\s+(.+)"),                          # 1 Summary (sin separador)
]

# Algunos modelos ponen el header en una línea y el summary en la siguiente:
#   "Acto 1 (nombre):\nLa familia..."  →  "Acto 1 (nombre): La familia..."
_HEADER_CONTINUATION = re.compile(
    r"^(Acto\s+\d+[^:]*:)\s*\n+\s*(.+)",
    re.MULTILINE,
)


def _normalize_multiline_beats(text: str) -> str:
    """Une encabezados 'Acto N:' solitarios con el texto de la línea siguiente."""
    return _HEADER_CONTINUATION.sub(r"\1 \2", text)


def parse_beats(text: str, num_beats: int, story_id=None, caller: str = "PARSER") -> list[Beat]:
    """Parser defensivo compartido. Activa FALLBACK si ningún patrón matchea."""
    beats = []
    seen_numbers: set[int] = set()

    text = _normalize_multiline_beats(text)

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        for pattern in _BEAT_PATTERNS:
            m = pattern.match(line)
            if m:
                beat_number = int(m.group(1))
                summary = m.group(2).strip()
                if summary and beat_number not in seen_numbers:
                    seen_numbers.add(beat_number)
                    beats.append(Beat(number=beat_number, summary=summary, status="pending"))
                break

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
