"""Configuración del paquete para el video (Spec-610), desde `config/video/`.

Cuatro archivos: la calabaza (`presentador.yaml`), lo que va en pantalla
(`biblia_visual.yaml`), quién lee (`lectores.yaml`) y el ritmo (`lectura.yaml`).
Se validan al cargar: un error de configuración se ve al arrancar, no a mitad de un job.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "config" / "video"

Narra = Literal["mujer", "hombre"]
TipoMomento = Literal["imagen", "animacion", "video"]


class Rango(BaseModel):
    desde: int = Field(ge=0)
    hasta: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordenado(self) -> "Rango":
        if self.desde > self.hasta:
            raise ValueError(f"rango invertido: {self.desde} > {self.hasta}")
        return self


class Intro(BaseModel):
    palabras: Rango
    guia: str


class Outro(BaseModel):
    palabras: Rango
    forma: list[str] = Field(min_length=1)
    cierra_con: str


class Presentador(BaseModel):
    nombre: str
    quien_es: str
    como_habla: str
    intro: Intro
    outro: Outro
    formato_voz: str
    ejemplos_outro: list[str] = Field(min_length=1)
    cierre_fijo: str = ""


class Tipo(BaseModel):
    nombre: str
    se_genera_con: str


class BibliaVisual(BaseModel):
    estilo: str
    formato: str
    momentos: Rango
    mezcla: dict[TipoMomento, float]
    videos: Rango
    tipos: dict[TipoMomento, Tipo]
    transiciones: list[str] = Field(min_length=1)
    palabras_prohibidas: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _completa(self) -> "BibliaVisual":
        todos = {"imagen", "animacion", "video"}
        if set(self.mezcla) != todos or set(self.tipos) != todos:
            raise ValueError("la mezcla y los tipos tienen que traer imagen, animacion y video")
        if abs(sum(self.mezcla.values()) - 1) > 0.01:
            raise ValueError(f"la mezcla tiene que sumar 1 (suma {sum(self.mezcla.values())})")
        if self.videos.hasta > self.momentos.desde:
            raise ValueError("no puede haber más videos que momentos")
        return self


class Lector(BaseModel):
    nombre: str
    narra: Narra


class Lectores(BaseModel):
    lectores: list[Lector] = Field(min_length=1)
    propuesta: dict[Narra, str]

    @model_validator(mode="after")
    def _propuesta_valida(self) -> "Lectores":
        por_nombre = {lector.nombre: lector for lector in self.lectores}
        for narra, nombre in self.propuesta.items():
            if nombre not in por_nombre:
                raise ValueError(f"la propuesta para «{narra}» no es un lector: {nombre}")
            if por_nombre[nombre].narra != narra:
                raise ValueError(f"{nombre} no lee cuando narra «{narra}»")
        return self

    def propuesto(self, narra: str) -> str | None:
        """Quién lee según quién narra; `None` si no se sabe."""
        return self.propuesta.get(narra)  # type: ignore[call-overload]


class Lectura(BaseModel):
    palabras_por_minuto: int = Field(gt=0)
    episodio_minutos: Rango


class VideoConfig(BaseModel):
    presentador: Presentador
    biblia: BibliaVisual
    lectores: Lectores
    lectura: Lectura


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_video_config(directory: Path = _DEFAULT_DIR) -> VideoConfig:
    """Lee y valida los cuatro archivos de `directory`."""
    return VideoConfig(
        presentador=Presentador(**_yaml(directory / "presentador.yaml")),
        biblia=BibliaVisual(**_yaml(directory / "biblia_visual.yaml")),
        lectores=Lectores(**_yaml(directory / "lectores.yaml")),
        lectura=Lectura(**_yaml(directory / "lectura.yaml")),
    )


@lru_cache
def video_config() -> VideoConfig:
    """La configuración de `config/video/` (una vez por proceso)."""
    return load_video_config()
