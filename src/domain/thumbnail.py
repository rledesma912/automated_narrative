"""La miniatura de una historia (Spec-790 §2.8, versión de hoy §10.7).

Una por historia: lo que cargó Yael, las piezas armadas (el personaje y el escenario, que se
reusan mientras no cambien el boceto ni la descripción) y las tandas de 4 opciones.
Los archivos viven en `miniaturas/<story_id>/`; acá solo los nombres.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.utils.timezone import now_argentina

Figura = Literal["entidad", "protagonista"]
Color = Literal["desaturado", "byn"]
TipoBoceto = Literal["personaje", "escenario"]


class ThumbnailInput(BaseModel):
    """Lo que carga Yael en el formulario."""

    figure: Figura = "entidad"
    figure_description: str = ""
    place_description: str = ""
    color: Color = "desaturado"  # D23
    tone: str = ""  # D25: vacío = el que propone el lugar
    character_sketch: str | None = None  # nombre del archivo en la carpeta de la historia
    scene_sketch: str | None = None


class Part(BaseModel):
    """Una pieza armada (interna): el personaje con alfa o el escenario."""

    file: str
    input_hash: str
    seconds: float = 0.0


class ImageTexts(BaseModel):
    """T3.3 (D28): lo que la IA separa de las dos descripciones de Yael, en inglés y en positivo."""

    personaje: str
    escenario: str
    relacion: str = ""
    a_medio_ver: Literal["no", "poco", "mucho"] = "no"
    input_hash: str = ""


class ThumbnailImage(BaseModel):
    """Una de las 4 opciones."""

    template: str  # la plantilla (D21)
    file: str
    fused: bool = True


class Batch(BaseModel):
    """Una tanda de 4."""

    n: int
    seed: int
    color: Color
    tone: str
    images: list[ThumbnailImage] = Field(default_factory=list)
    seconds: float = 0.0
    created_at: datetime = Field(default_factory=now_argentina)


class Thumbnail(BaseModel):
    """La miniatura de una historia."""

    story_id: str
    input: ThumbnailInput = Field(default_factory=ThumbnailInput)
    parts: dict[str, Part] = Field(default_factory=dict)  # "personaje" | "escenario" | "importante"
    texts: ImageTexts | None = None  # T3.3: se reusa mientras no cambien las descripciones
    batches: list[Batch] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=now_argentina)

    @property
    def last_batch(self) -> Batch | None:
        return self.batches[-1] if self.batches else None
