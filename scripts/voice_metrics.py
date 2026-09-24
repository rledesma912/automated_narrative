"""Métricas de la prosa de la Voz (Spec-470 §2). Funciones puras sobre el texto."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.application.services.voice_cliches import load_cliches  # noqa: E402

# Parentescos con sus sinónimos: "mi mamá" vale lo mismo que "mi madre".
KINSHIP = {
    "madre": ("madre", "mamá", "mama"),
    "padre": ("padre", "papá", "papa"),
    "abuela": ("abuela",),
    "abuelo": ("abuelo",),
    "suegra": ("suegra",),
    "suegro": ("suegro",),
    "esposo": ("esposo", "marido"),
    "esposa": ("esposa",),
    "hijo": ("hijo",),
    "hija": ("hija",),
    "hermano": ("hermano",),
    "hermana": ("hermana",),
    "tío": ("tío", "tio"),
    "tía": ("tía", "tia"),
}

_QUOTED = re.compile(r"“[^”]*”|\"[^\"]*\"|«[^»]*»")


def split_acts(text: str) -> list[str]:
    """Relato consolidado → actos (separados por `## Acto N`)."""
    parts = re.split(r"^## Acto \d+\s*$", text, flags=re.M)
    return [p.strip() for p in parts[1:]] if len(parts) > 1 else [text]


def narration_only(text: str) -> str:
    """Quita el diálogo: texto entre comillas y líneas que arrancan con raya."""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(("—", "–", "-"))]
    return _QUOTED.sub(" ", "\n".join(lines))


def dialogue_only(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.lstrip().startswith(("—", "–", "-"))]
    return "\n".join(lines + _QUOTED.findall(text))


def cliches(text: str, expressions: list[str] | None = None) -> dict[str, int]:
    """Conteo por cliché. Las expresiones largas se cuentan primero y no se cuentan dos veces
    («se me heló la sangre» no suma también «me heló la sangre»)."""
    low = text.lower()
    counts: dict[str, int] = {}
    for expr in sorted(
        expressions if expressions is not None else load_cliches(), key=len, reverse=True
    ):
        n = low.count(expr)
        if n:
            counts[expr] = n
            low = low.replace(expr, " ")
    return counts


def valid_kinship(narrator: str, cast: list[dict]) -> set[str]:
    """Parentescos que alguien tiene *con el narrador*, según su rol («Suegra de Irene»)."""
    valid = set()
    for person in cast:
        role = (person.get("role") or "").lower()
        for kin, words in KINSHIP.items():
            for w in words:
                if re.search(rf"\b{w}\b[^;.]*?\bde {narrator.lower()}\b", role):
                    valid.add(kin)
        # «Bebé de Irene» es hijo o hija de Irene.
        if re.search(rf"\bbeb[eé]\b[^;.]*?\bde {narrator.lower()}\b", role):
            valid |= {"hijo", "hija"}
    return valid


def _kin_mentions(text: str) -> dict[str, int]:
    low = text.lower()
    found: dict[str, int] = {}
    for kin, words in KINSHIP.items():
        n = sum(len(re.findall(rf"\bmi {w}\b", low)) for w in words)
        if n:
            found[kin] = n
    return found


def wrong_kinship(text: str, narrator: str, cast: list[dict]) -> dict[str, dict[str, int]]:
    """«mi <parentesco>» que nadie tiene con el narrador.

    `narracion` es la métrica (la voz del narrador). `dialogo` va aparte, a revisar a
    mano: ahí puede hablar otro personaje («mi madre» dicho por el hijo es correcto).
    """
    valid = valid_kinship(narrator, cast)

    def wrong(fragment: str) -> dict[str, int]:
        return {k: n for k, n in _kin_mentions(fragment).items() if k not in valid}

    return {"narracion": wrong(narration_only(text)), "dialogo": wrong(dialogue_only(text))}


def narrator_outside_dialogue(text: str, narrator: str) -> int:
    """Veces que aparece el nombre del narrador fuera de diálogo (narración en 3ra persona)."""
    return len(re.findall(rf"\b{re.escape(narrator)}\b", narration_only(text)))


def repeated_4grams(acts: list[str], min_acts: int = 3) -> list[str]:
    """4-gramas (en minúsculas) presentes en al menos `min_acts` actos."""

    def grams(act: str) -> set[str]:
        words = re.findall(r"\w+", act.lower())
        return {" ".join(words[i : i + 4]) for i in range(len(words) - 3)}

    per_act = [grams(a) for a in acts]
    everything = set().union(*per_act) if per_act else set()
    return sorted(g for g in everything if sum(g in ga for ga in per_act) >= min_acts)


def evaluate(text: str, narrator: str, cast: list[dict]) -> dict:
    """Todas las métricas de un relato consolidado."""
    kin = wrong_kinship(text, narrator, cast)
    found = cliches(text)
    return {
        "palabras": len(text.split()),
        "cliches": sum(found.values()),
        "cliches_detalle": found,
        "parentescos_mal": sum(kin["narracion"].values()),
        "parentescos_en_dialogo": kin["dialogo"],
        "narrador_3ra_persona": narrator_outside_dialogue(text, narrator),
        "frases_repetidas": len(repeated_4grams(split_acts(text))),
    }
