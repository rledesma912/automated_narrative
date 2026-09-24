"""Lista de clichés prohibidos para la Voz (Spec-470 §1.1).

Vive en `config/prompts_generation/voice_cliches.txt` (un único lugar): la usan
el prompt de la Voz y las métricas de la evaluación.
"""

from pathlib import Path

from src.config import settings

CLICHES_FILE = "voice_cliches.txt"


def load_cliches(path: Path | None = None) -> list[str]:
    """Expresiones en minúsculas, sin comentarios (`#`), líneas vacías ni duplicados."""
    path = path or Path(settings.prompts_dir) / CLICHES_FILE
    if not path.exists():
        return []
    seen: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        expr = line.strip().lower()
        if expr and not expr.startswith("#") and expr not in seen:
            seen.append(expr)
    return seen
