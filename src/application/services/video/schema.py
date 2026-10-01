"""Lo que devuelve la IA al armar el paquete (Spec-610 §3.2), validado con Pydantic.

La IA no devuelve texto del relato: devuelve rangos de párrafos por acto. Los énfasis
son frases copiadas del bloque; el código las busca y las pasa a posiciones. El tipo
de cada momento (imagen, animación o video) no lo elige la IA: lo reparte el código.
Qué va en cada campo lo dice el prompt (`config/prompts_generation/video_script.md`).
"""

from typing import Literal

from pydantic import BaseModel


class BloqueIA(BaseModel):
    acto: int
    desde: int
    hasta: int
    indicacion: str
    enfasis: list[str]
    pausa: Literal["ninguna", "corta", "larga"]


class MomentoIA(BaseModel):
    acto: int
    desde: int
    hasta: int
    fuerte: bool
    que_se_ve: str
    lugar: str
    prompt_imagen: str
    prompt_movimiento: str
    transicion: str
    sonido: str


class PaqueteIA(BaseModel):
    narra: Literal["mujer", "hombre", "no_se_sabe"]
    bloques: list[BloqueIA]
    momentos: list[MomentoIA]
    intro: str
    outro: str
