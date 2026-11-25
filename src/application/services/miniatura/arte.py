"""El arte común de las miniaturas: `config/miniatura/arte.yaml` (Spec-790 D6, D17, §10.7).

Lo valida un modelo al cargar: 4 plantillas (D21), tonos con 3 colores, el tono por defecto que
exista. Los prompts de cada paso viven en `config/miniatura/prompts/<paso>.md` (D17).
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from src.messages import message

CONFIG = Path("config/miniatura")

Rgb = Annotated[list[int], Field(min_length=3, max_length=3)]


class Lienzo(BaseModel):
    ancho: int = 1280
    alto: int = 720
    calidad_jpg: int = 90


class Plantilla(BaseModel):
    nombre: str
    cx: float = Field(ge=0, le=1)
    alto: float = Field(gt=0, le=1.5)
    recorte: float = Field(gt=0, le=1)


class Escenario(BaseModel):
    gamma: float = 1.6
    techo: float = 0.75
    cambio_foto: float = 0.75  # T6.6 (E11i): con el boceto de guía, Z-Image reinterpreta todo
    guia: float = Field(default=0.6, ge=0, le=1)  # fuerza del ControlNet; a 0,8 vuelven las manchas


class PersonajeArte(BaseModel):
    cambio_foto: float = Field(default=0.50, ge=0, le=1)  # E11: Z-Image sobre el personaje


class MedioVer(BaseModel):
    desde: float = Field(ge=0, le=1)  # desde qué altura de la figura empieza a perderse
    queda: float = Field(ge=0, le=1)  # cuánto se ve en los pies


class FiguraArte(BaseModel):
    veces_el_lugar: float = 1.7
    techo: float = 0.80
    piso: float = 30
    grano: float = 4
    anillo: float = 0.04
    # T6.4: la figura se pierde en la sombra del lugar según `relacion.a_medio_ver` (T3.3)
    sombra: float = 0.35
    sombra_difuminado: float = 0.15  # radio, en proporción al alto de la figura
    medio_ver: dict[str, MedioVer] = Field(default_factory=dict)


class Fundido(BaseModel):
    dilatacion: float = 0.01
    borde: int = 16
    margen: float = 0.12
    # T6.7: las plantillas donde la figura escondida se funde con algo delante (tanda 6: en el
    # primer plano el tronco le tapaba la cara y en la chica Qwen duplicaba la cabeza)
    detras_en: list[str] = Field(default_factory=list)


class ColorArte(BaseModel):
    tope_desaturado: float = 40


class Tono(BaseModel):
    nombre: str
    colores: Annotated[list[Rgb], Field(min_length=3, max_length=3)]
    fuerza: float = Field(ge=0, le=1)
    figura: bool = False  # Halloween: se tiñe la figura y el fondo queda gris
    lugares: list[str] = Field(default_factory=list)


class Arte(BaseModel):
    lienzo: Lienzo = Field(default_factory=Lienzo)
    plantillas: dict[str, Plantilla]
    escenario: Escenario = Field(default_factory=Escenario)
    personaje: PersonajeArte = Field(default_factory=PersonajeArte)
    figura: FiguraArte = Field(default_factory=FiguraArte)
    fundido: Fundido = Field(default_factory=Fundido)
    color: ColorArte = Field(default_factory=ColorArte)
    tonos: dict[str, Tono]
    tono_por_defecto: str

    @field_validator("plantillas")
    @classmethod
    def _cuatro(cls, v: dict) -> dict:
        if len(v) != 4:
            raise ValueError(message("miniatura.arte_cuatro_plantillas"))
        return v

    @model_validator(mode="after")
    def _tono(self) -> "Arte":
        if self.tono_por_defecto not in self.tonos:
            raise ValueError(message("miniatura.arte_tono_inexistente", tono=self.tono_por_defecto))
        return self

    def tono_del_lugar(self, descripcion: str) -> str:
        """D25: el tono que propone el lugar (la primera palabra del catálogo que aparece)."""
        texto = f" {descripcion.lower()} "
        # las excepciones (Halloween: la figura teñida) ganan a los tonos del lugar
        orden = sorted(self.tonos.items(), key=lambda kv: not kv[1].figura)
        for clave, tono in orden:
            if any(lugar.lower() in texto for lugar in tono.lugares):
                return clave
        return self.tono_por_defecto

    def tono_valido(self, tono: str, descripcion: str) -> str:
        return tono if tono in self.tonos else self.tono_del_lugar(descripcion)


@lru_cache(maxsize=1)
def arte() -> Arte:
    return Arte.model_validate(yaml.safe_load((CONFIG / "arte.yaml").read_text(encoding="utf-8")))


@lru_cache(maxsize=8)
def _plantilla_prompt(paso: str) -> str:
    return (CONFIG / "prompts" / f"{paso}.md").read_text(encoding="utf-8").strip()


def texto(paso: str, **datos: str) -> str:
    """Una plantilla de `prompts/` con sus huecos `{clave}` llenos (T3.3)."""
    out = _plantilla_prompt(paso)
    for clave, valor in datos.items():
        out = out.replace("{" + clave + "}", valor.strip())
    return out


def prompt(paso: str, descripcion: str = "") -> str:
    """El prompt de un paso con la descripción de la historia (D17)."""
    return _plantilla_prompt(paso).replace("{descripcion}", descripcion.strip())
