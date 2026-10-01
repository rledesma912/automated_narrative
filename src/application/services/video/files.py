"""Nombres de archivo del mapa de producción (Spec-610 §3.7.4): `06-ventanilla.png`.

El número va primero para que en la carpeta queden en el orden del video.
"""

import re
import unicodedata

EXTENSIONES = {"imagen": ("png",), "animacion": ("png", "mp4"), "video": ("png", "mp4")}


def slug(text: str, limit: int = 30) -> str:
    """Minúsculas, sin tildes ni espacios: «Borde del bosque» → `borde-del-bosque`."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    words = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
    if len(words) > limit:  # cortar en el último guion, no a mitad de palabra
        cut = words[: limit + 1]
        words = cut.rsplit("-", 1)[0] if "-" in cut else words[:limit]
    return words or "momento"


def base_name(number: int, place: str) -> str:
    return f"{number:02d}-{slug(place)}"


def file_names(number: int, place: str, kind: str) -> list[str]:
    """Los archivos que hay que generar para el momento (`png`, y `mp4` si se mueve)."""
    base = base_name(number, place)
    return [f"{base}.{ext}" for ext in EXTENSIONES[kind]]
