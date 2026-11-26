"""El tablero (Spec-795): entregas que publica Claude y las opiniones sobre cada archivo."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

TipoOpinion = Literal["me_gusta", "no_va", "nota"]
TipoMedio = Literal["imagen", "audio", "video"]

_MEDIOS: dict[str, TipoMedio] = {"mp3": "audio", "wav": "audio", "mp4": "video"}


def tipo_medio(archivo: str) -> TipoMedio:
    return _MEDIOS.get(archivo.rsplit(".", 1)[-1].lower(), "imagen")


class Archivo(BaseModel):
    archivo: str
    leyenda: str = ""


class Fila(BaseModel):
    titulo: str = ""
    imagenes: list[Archivo] = Field(min_length=1)


class Entrega(BaseModel):
    id: str  # el nombre de la carpeta: AAAA-MM-DD-slug
    titulo: str = Field(min_length=1)
    proyecto: str = Field(min_length=1)
    fecha: date
    que_mirar: str = ""
    filas: list[Fila] = []
    imagenes: list[Archivo] = []  # las sueltas, fuera de las filas

    def archivos(self) -> list[Archivo]:
        return [a for f in self.filas for a in f.imagenes] + list(self.imagenes)

    def tiene(self, archivo: str) -> bool:
        return any(a.archivo == archivo for a in self.archivos())


class Opinion(BaseModel):
    id: int
    entrega: str
    archivo: str
    tipo: TipoOpinion
    texto: str = ""
    created_at: datetime
    navegador: str = ""  # D6: el id que guarda cada navegador ("" en las de antes)
