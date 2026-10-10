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


class RangosDelLargo(BaseModel):
    """Spec-650: momentos y videos de un largo que no es el de siempre (el corto)."""

    momentos: Rango
    videos: Rango

    @model_validator(mode="after")
    def _videos_entran(self) -> "RangosDelLargo":
        if self.videos.hasta > self.momentos.desde:
            raise ValueError("no puede haber más videos que momentos")
        return self


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
    # Spec-650: `momentos` y `videos` de arriba son los del largo; acá, los de los demás.
    por_estructura: dict[str, RangosDelLargo] = {}

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

    def para(self, estructura: str) -> "BibliaVisual":
        """Spec-650: la biblia con los momentos y videos del largo del relato."""
        rangos = self.por_estructura.get(estructura)
        if rangos is None:
            return self
        return self.model_copy(update={"momentos": rangos.momentos, "videos": rangos.videos})


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
    episodio_minutos: Rango  # el del largo
    episodio_por_estructura: dict[str, Rango] = {}  # Spec-650: el de los demás (el corto)

    def episodio(self, estructura: str) -> Rango:
        """Spec-650: cuánto dura un episodio del largo del relato."""
        return self.episodio_por_estructura.get(estructura, self.episodio_minutos)


class VideoConfig(BaseModel):
    presentador: Presentador
    biblia: BibliaVisual
    lectores: Lectores
    lectura: Lectura

    @model_validator(mode="after")
    def _cada_largo_tiene_sus_rangos(self) -> "VideoConfig":
        """Spec-650: un largo sin sus rangos usaría los del largo de siempre sin avisar."""
        from src.application.services.beat_spec_repository import BeatSpecRepository
        from src.application.services.structure import DEFAULT_STRUCTURE

        otros = set(BeatSpecRepository().structure_ids) - {DEFAULT_STRUCTURE}
        for nombre, tiene in (
            ("biblia_visual.yaml: por_estructura", set(self.biblia.por_estructura)),
            ("lectura.yaml: episodio_por_estructura", set(self.lectura.episodio_por_estructura)),
        ):
            if tiene != otros:
                raise ValueError(f"{nombre} tiene que traer {sorted(otros)} (trae {sorted(tiene)})")
        return self


def estructura_del_relato(cantidad_de_actos: int) -> str:
    """Spec-650: el largo de un relato guardado, por cuántos actos tiene (una versión puede
    ser de cuando la historia tenía otro largo). Una cantidad rara se toma como larga."""
    from src.application.services.beat_spec_repository import BeatSpecRepository
    from src.application.services.structure import DEFAULT_STRUCTURE

    repo = BeatSpecRepository()
    for sid in repo.structure_ids:
        if repo.estructura(sid).num_actos == cantidad_de_actos:
            return sid
    return DEFAULT_STRUCTURE


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
