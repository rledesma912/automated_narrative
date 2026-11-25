"""T3.3 (D27, D28): la IA separa lo que escribió Yael en el personaje solo, el lugar vacío y la
relación entre los dos, en inglés y en positivo. Los modelos de imagen dibujan todo lo que se
nombra y no entienden el «no» (cfg 1), así que nada crudo llega a ellos (E11c).

T6.5 (E11e): además mira los dos bocetos (primero el personaje, después el lugar) y nombra cada
cosa dibujada como lo que es de verdad: Qwen copia las formas tal cual y una planta ambigua
salía «fotografiada» como una persona.
"""

import io
from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps
from pydantic import BaseModel

from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.miniatura.arte import texto
from src.domain.interfaces import ImagenEntrada, LLMProvider
from src.domain.thumbnail import ImageTexts, ThumbnailInput

ROLE = "miniatura"
# Lado mayor de un boceto para la IA: alcanza para ver el trazo y queda lejos de los topes de
# las API (Claude reduce a ~1 568 px y no acepta más de 5 MB por imagen).
LADO_MAX = 1536


class _Salida(BaseModel):
    personaje: str
    escenario: str
    relacion: str
    a_medio_ver: Literal["no", "poco", "mucho"]


def pedido(i: ThumbnailInput) -> str:
    return texto("ia_pedido", personaje=i.figure_description, lugar=i.place_description)


def boceto_para_la_ia(ruta: Path) -> ImagenEntrada:
    """El boceto en JPG, con el lado mayor en `LADO_MAX` como mucho."""
    with Image.open(ruta) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            fondo = Image.new("RGB", im.size, "white")  # el papel, si el PNG trae transparencia
            fondo.paste(im.convert("RGBA"), mask=im.convert("RGBA").getchannel("A"))
            im = fondo
        im = im.convert("RGB")
        im.thumbnail((LADO_MAX, LADO_MAX))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
    return ImagenEntrada(data=buf.getvalue(), media_type="image/jpeg")


async def separar(
    llm: LLMProvider,
    i: ThumbnailInput,
    input_hash: str,
    bocetos: list[Path] | None = None,
) -> ImageTexts:
    r, _ = await generate_structured(
        llm,
        role=ROLE,
        prompt=pedido(i),
        system_prompt=texto("ia_sistema"),
        output=_Salida,
        images=[boceto_para_la_ia(b) for b in bocetos or []],
    )
    return ImageTexts(
        personaje=" ".join(r.personaje.split()),
        escenario=" ".join(r.escenario.split()),
        relacion=" ".join(r.relacion.split()),
        a_medio_ver=r.a_medio_ver,
        input_hash=input_hash,
    )
