"""Reparto al azar de los tipos de momento (Spec-610 §3.4): lo hace el código, no la IA.

Con una semilla por variante: el mismo relato da siempre el mismo mapa. La mezcla viene
de `config/video/biblia_visual.yaml`. Reglas: entre `videos.desde` y `videos.hasta`
videos, nunca dos videos seguidos, y los momentos fuertes son video o animación (el
primero de ellos, video).
"""

import random

from src.application.services.video.config import BibliaVisual


def seed_for(narrative_id) -> int:
    """La semilla de una variante: su id como número."""
    return narrative_id.int % (2**31)


def assign(strong: list[bool], biblia: BibliaVisual, seed: int) -> list[str]:
    """El tipo de cada momento, en orden. `strong[i]`: el momento i es de los fuertes."""
    n = len(strong)
    if not n:
        return []
    rng = random.Random(seed)
    videos = min(max(round(n * biblia.mezcla["video"]), biblia.videos.desde), biblia.videos.hasta)
    videos = min(videos, (n + 1) // 2)  # sin dos seguidos, no entran más
    animations = min(round(n * biblia.mezcla["animacion"]), n - videos)
    types = ["imagen"] * n

    def can_be_video(i: int) -> bool:
        return types[i] == "imagen" and all(
            types[j] != "video" for j in (i - 1, i + 1) if 0 <= j < n
        )

    strong_idx = [i for i, s in enumerate(strong) if s]
    if strong_idx and videos:
        types[strong_idx[0]] = "video"
        videos -= 1
    candidates = [i for i in range(n) if types[i] == "imagen"]
    rng.shuffle(candidates)
    for i in candidates:
        if not videos:
            break
        if can_be_video(i):
            types[i] = "video"
            videos -= 1

    # Los fuertes que quedaron como imagen pasan a animación; después, al azar.
    for i in strong_idx:
        if animations and types[i] == "imagen":
            types[i] = "animacion"
            animations -= 1
    rest = [i for i in range(n) if types[i] == "imagen"]
    rng.shuffle(rest)
    for i in rest[:animations]:
        types[i] = "animacion"
    return types
