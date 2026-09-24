"""Qué manifestaciones de una entidad ve la Voz en cada acto (Spec-450 §10).

Determinístico, sin LLM: cada manifestación queda reservada para el primer acto
cuya sinopsis la menciona. En las exposiciones tempranas la Voz no recibe las
reservadas para un acto posterior, así no las adelanta.
"""

import re

_MIN_LEN = 5  # palabras significativas: ≥ 5 letras, comparadas por sus primeras 5
_MIN_SHARED = 2
_STOPWORDS = {
    "antes", "cuando", "desde", "después", "donde", "entre", "estaba", "hasta",
    "hacia", "mientras", "porque", "sobre", "tiene", "todos", "todas", "otra", "algo",
}  # fmt: skip


def split_manifestations(text: str) -> list[str]:
    """«El caballo se clava; olor a tierra mojada.» → ítems."""
    return [item.strip() for item in re.split(r"[;.]", text or "") if item.strip()]


def _keys(text: str) -> set[str]:
    words = re.findall(r"\w+", text.lower())
    return {w[:_MIN_LEN] for w in words if len(w) >= _MIN_LEN and w not in _STOPWORDS}


def reserved_act(item: str, act_texts: list[str]) -> int | None:
    """Primer acto (1..N) cuya sinopsis comparte ≥ 2 palabras significativas con el ítem."""
    keys = _keys(item)
    for number, text in enumerate(act_texts, start=1):
        if len(keys & _keys(text)) >= _MIN_SHARED:
            return number
    return None


def manifestations_for_act(
    text: str, beat_number: int, act_texts: list[str], limit: int
) -> list[str]:
    """Ítems que la Voz puede usar en el acto: primero los de este acto, después los
    libres; nunca los reservados para un acto posterior. Hasta `limit`."""
    this_act, free = [], []
    for item in split_manifestations(text):
        act = reserved_act(item, act_texts)
        if act == beat_number:
            this_act.append(item)
        elif act is None or act < beat_number:
            free.append(item)
    return (this_act + free)[:limit]
