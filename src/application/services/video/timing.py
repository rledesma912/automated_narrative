"""Tiempos del episodio (Spec-610 §3.2): palabras / ritmo de lectura, sin IA.

La web hace la misma cuenta en `frontend/public/js/tiempos.js`; los dos pasan los casos
de `tests/fixtures/video/tiempos_casos.json`. Por eso el redondeo es «la mitad para
arriba» (como `Math.round`) y no el de Python, que redondea al par.
"""

import math
from typing import Literal

EstadoEpisodio = Literal["corto", "entra", "largo"]


def palabras(texto: str) -> int:
    """Cantidad de palabras: lo que hay entre espacios, tabulaciones o saltos de línea."""
    return len(texto.split())


def segundos(cantidad_palabras: int, palabras_por_minuto: int) -> int:
    """Segundos que lleva leer `cantidad_palabras` al ritmo dado."""
    return math.floor(cantidad_palabras / palabras_por_minuto * 60 + 0.5)


def reloj(total_segundos: int) -> str:
    """`m:ss`, como en un reproductor («15:36»)."""
    return f"{total_segundos // 60}:{total_segundos % 60:02d}"


def largo(total_segundos: int) -> str:
    """Para leer: «45 s», «1 min», «3 min 11 s»."""
    minutos, resto = divmod(total_segundos, 60)
    if not minutos:
        return f"{resto} s"
    return f"{minutos} min" if not resto else f"{minutos} min {resto:02d} s"


def episodio(total_segundos: int, desde_min: int, hasta_min: int) -> EstadoEpisodio:
    """Si el episodio no llega, entra o se pasa del largo del canal."""
    if total_segundos < desde_min * 60:
        return "corto"
    if total_segundos > hasta_min * 60:
        return "largo"
    return "entra"
