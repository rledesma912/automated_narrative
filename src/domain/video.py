"""El paquete para el video (Spec-610): guion de lectura, la calabaza y el mapa.

El paquete no copia el texto del relato: bloques y momentos apuntan a **párrafos dentro
de un acto** (1 = el primer párrafo del acto) y cada vista lee el relato actual. Las
marcas de remarcado apuntan a palabras dentro de su bloque y guardan también su texto,
para reubicarlas si el relato se corrigió (Spec-610 §7.2).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import UUID4, BaseModel, Field, model_validator

from src.utils.timezone import now_argentina

Pausa = Literal["ninguna", "corta", "larga"]
TipoMomento = Literal["imagen", "animacion", "video"]
Narra = Literal["mujer", "hombre", "no_se_sabe"]


class _Rango(BaseModel):
    """Párrafos `desde`..`hasta` (incluidos) del acto `acto`, contados desde 1."""

    acto: int = Field(ge=1)
    desde: int = Field(ge=1)
    hasta: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordenado(self):
        if self.desde > self.hasta:
            raise ValueError(f"rango invertido en el acto {self.acto}: {self.desde} > {self.hasta}")
        return self


class Mark(BaseModel):
    """Palabras `desde_palabra`..`hasta_palabra` (desde 0) del bloque, remarcadas."""

    desde_palabra: int = Field(ge=0)
    hasta_palabra: int = Field(ge=0)
    texto: str


class ReadingBlock(_Rango):
    """Un bloque del guion de lectura."""

    indicacion: str = ""
    pausa: Pausa = "corta"
    marcas: list[Mark] = Field(default_factory=list)


class VisualMoment(_Rango):
    """Un momento del mapa de producción: lo que va en pantalla mientras se lee."""

    fuerte: bool = False
    tipo: TipoMomento = "imagen"
    que_se_ve: str
    lugar: str  # para el nombre del archivo (`06-ventanilla.png`)
    prompt_imagen: str
    prompt_movimiento: str = ""
    transicion: str
    sonido: str = ""


class PresenterLines(BaseModel):
    """Lo que dice la calabaza de la cripta."""

    intro: str
    outro: str


class VideoScript(BaseModel):
    """El paquete de una variante del relato."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    narrative_id: UUID4
    narra: Narra = "no_se_sabe"
    lector: str | None = None
    bloques: list[ReadingBlock]
    momentos: list[VisualMoment]
    calabaza: PresenterLines
    # Cómo estaba el relato al armarlo (Spec-610 §7.2: estado frente al relato).
    parrafos_por_acto: dict[int, int]
    narrative_hash: str
    seed: int
    created_at: datetime = Field(default_factory=now_argentina)
    updated_at: datetime = Field(default_factory=now_argentina)

    def data(self) -> dict:
        """Lo que se guarda en la columna JSON `data` (lo que se edita)."""
        return self.model_dump(
            mode="json", include={"narra", "lector", "bloques", "momentos", "calabaza"}
        )
