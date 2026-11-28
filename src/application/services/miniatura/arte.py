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
    # Spec-820 D3: «respeta» el boceto o lo «reinterpreta» (cuánto cambia la foto única)
    modo: str = "respeta"
    fuerza: float | None = Field(default=None, ge=0, le=1)  # pisa la del modo


class Modo(BaseModel):
    """Spec-820: la pasada única de Z-Image (`foto_controlnet`) sobre la composición."""

    cambio: float = Field(ge=0, le=1)  # denoise
    fuerza: float = Field(ge=0, le=1)  # el ControlNet con la guía de profundidad


class Escenario(BaseModel):
    gamma: float = 1.6
    techo: float = 0.75
    cambio_foto: float = 0.75  # T6.6 (E11i): con el boceto de guía, Z-Image reinterpreta todo
    guia: float = Field(default=0.6, ge=0, le=1)  # fuerza del ControlNet; a 0,8 vuelven las manchas


class PersonajeArte(BaseModel):
    cambio_foto: float = Field(default=0.50, ge=0, le=1)  # E11: Z-Image sobre el personaje


class Fundido(BaseModel):
    dilatacion: float = 0.01
    borde: int = 16
    margen: float = 0.12
    # T6.7 → Spec-820: las plantillas donde la figura escondida va detrás de un tronco (tanda 6:
    # en el primer plano el tronco le tapaba la cara y en la chica se duplicaba la cabeza)
    detras_en: list[str] = Field(default_factory=list)


class ColorArte(BaseModel):
    tope_desaturado: float = 40


class Tono(BaseModel):
    nombre: str
    colores: Annotated[list[Rgb], Field(min_length=3, max_length=3)]
    fuerza: float = Field(ge=0, le=1)
    figura: bool = False  # Halloween: se tiñe la figura y el fondo queda gris
    lugares: list[str] = Field(default_factory=list)


class Niebla(BaseModel):
    """S0: lo que ya es claro y difuso del fondo (lo lejano) se vuelve niebla blanca."""

    gris: int = 200
    desde: int = 30
    rango: int = 90
    fuerza: float = 0.85
    difuminado: int = 40
    piso_abajo: float = 0.25  # abajo (lo cercano) entra menos niebla
    oscuro: float = 0.55  # lo que no es niebla se oscurece (troncos cercanos en silueta)


class Halo(BaseModel):
    radio: float = 0.10  # del alto del cuadro
    difuminado: float = 0.06
    fuerza: float = 0.75
    color: Rgb = Field(default_factory=lambda: [232, 236, 240])


class Tronco(BaseModel):
    """S1c: el tronco que tapa a la figura escondida, en proporción a la caja de la figura."""

    centro: float = 0.42
    ancho: float = 0.36
    abajo: float = 1.15  # cuánto se ensancha hacia abajo
    oscuro: list[int] = Field(default_factory=lambda: [22, 58], min_length=2, max_length=2)


class Control(BaseModel):
    """Después de la foto: niveles y niebla (Python controla, no pinta)."""

    negro: float = 1.0  # % que se recorta en el negro
    blanco: float = 0.3
    niebla_desde: int = 50
    niebla_rango: int = 80
    niebla_fuerza: float = 0.7
    niebla_color: Rgb = Field(default_factory=lambda: [150, 158, 165])


class Despegar(BaseModel):
    anillo: float = 0.05
    difuminado: float = 0.04
    fuerza: float = 0.6
    color: Rgb = Field(default_factory=lambda: [90, 95, 100])


class Mate(BaseModel):
    """D7: dentro de la figura las luces se aplastan (salvo los ojos y el borde)."""

    techo: int = 42
    compresion: float = 0.25
    nucleo: float = 0.012


class Luz(BaseModel):
    """Spec-820: la luz de Yael (figura oscura contra niebla clara, despegada)."""

    niebla: Niebla = Field(default_factory=Niebla)
    silueta_techo: int = 55
    silueta_factor: float = 0.3
    ojos_umbral: int = 170
    ojos_color: Rgb = Field(default_factory=lambda: [255, 215, 70])
    halo: Halo = Field(default_factory=Halo)
    profundidad_gamma: float = 2.2
    profundidad_anillo: float = 0.07
    tronco: Tronco = Field(default_factory=Tronco)
    control: Control = Field(default_factory=Control)
    despegar: Despegar = Field(default_factory=Despegar)
    mate: Mate = Field(default_factory=Mate)


class Arte(BaseModel):
    lienzo: Lienzo = Field(default_factory=Lienzo)
    plantillas: dict[str, Plantilla]
    escenario: Escenario = Field(default_factory=Escenario)
    personaje: PersonajeArte = Field(default_factory=PersonajeArte)
    fundido: Fundido = Field(default_factory=Fundido)
    color: ColorArte = Field(default_factory=ColorArte)
    modos: dict[str, Modo] = Field(default_factory=dict)
    luz: Luz = Field(default_factory=Luz)
    # D8: palabras que, si aparecen en un prompt de la IA, se dibujan (la cámara, una luna que no
    # está en el lugar). La clave es la palabra; el valor, las del lugar que la permiten.
    se_dibujan: dict[str, list[str]] = Field(default_factory=dict)
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
        for p in self.plantillas.values():
            if p.modo not in self.modos:
                raise ValueError(message("miniatura.arte_modo_inexistente", modo=p.modo))
        return self

    def foto(self, clave: str) -> tuple[float, float]:
        """Spec-820: (cambio, fuerza) de la pasada única de una plantilla."""
        p = self.plantillas[clave]
        m = self.modos[p.modo]
        return m.cambio, p.fuerza if p.fuerza is not None else m.fuerza

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
