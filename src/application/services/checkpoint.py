"""Checkpoint validation and phase labels for --hasta pipeline control (Spec-040)."""

VALID_CHECKPOINTS: dict[str, int] = {
    "analyst":    1,
    "mapper:1":   2,  "voz:1":   3,  "journal:1":   4,
    "mapper:2":   5,  "voz:2":   6,  "journal:2":   7,
    "mapper:3":   8,  "voz:3":   9,  "journal:3":  10,
    "mapper:4":  11,  "voz:4":  12,  "journal:4":  13,
    "mapper:5":  14,  "voz:5":  15,  "journal:5":  16,
}

PHASE_LABELS: dict[str, str] = {
    "analyst":    "🔍  Analyst          — Extrayendo anclajes",
    "mapper:1":   "🗺   Mapper  · Beat 1 — Mapeando acto 1",
    "voz:1":      "✍️   Voz     · Beat 1 — Narrando acto 1",
    "journal:1":  "📓  Journal · Beat 1 — Registrando memoria",
    "mapper:2":   "🗺   Mapper  · Beat 2 — Mapeando acto 2",
    "voz:2":      "✍️   Voz     · Beat 2 — Narrando acto 2",
    "journal:2":  "📓  Journal · Beat 2 — Registrando memoria",
    "mapper:3":   "🗺   Mapper  · Beat 3 — Mapeando acto 3",
    "voz:3":      "✍️   Voz     · Beat 3 — Narrando acto 3",
    "journal:3":  "📓  Journal · Beat 3 — Registrando memoria",
    "mapper:4":   "🗺   Mapper  · Beat 4 — Mapeando acto 4",
    "voz:4":      "✍️   Voz     · Beat 4 — Narrando acto 4",
    "journal:4":  "📓  Journal · Beat 4 — Registrando memoria",
    "mapper:5":   "🗺   Mapper  · Beat 5 — Mapeando acto 5",
    "voz:5":      "✍️   Voz     · Beat 5 — Narrando acto 5",
    "journal:5":  "📓  Journal · Beat 5 — Registrando memoria",
}

_ORDERED = sorted(VALID_CHECKPOINTS, key=VALID_CHECKPOINTS.__getitem__)


def validate(value: str) -> None:
    """Lanza ValueError con listado de valores válidos si el checkpoint no existe."""
    if value not in VALID_CHECKPOINTS:
        raise ValueError(
            f"checkpoint inválido '{value}'. Valores válidos:\n  "
            + "\n  ".join(_ORDERED)
        )


def ordinal(value: str) -> int:
    """Retorna la posición ordinal (1-16) del checkpoint."""
    return VALID_CHECKPOINTS[value]


def label(value: str) -> str:
    """Retorna el label legible para mostrar en consola."""
    return PHASE_LABELS.get(value, value)
