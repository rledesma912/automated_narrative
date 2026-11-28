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
from pydantic import BaseModel, create_model

from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.miniatura.arte import Arte, texto
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


# ── Spec-820 S2: los prompts de la foto única ─────────────────────────────────────
class _Foto(BaseModel):
    prompt: str
    luz: str  # qué luz y qué cobertura eligió, en castellano (para el registro)


def _salida_fotos(claves: list[str]) -> type[BaseModel]:
    return create_model("_Fotos", **{k: (_Foto, ...) for k in claves})


def foto_fija(t: ImageTexts, detras: bool) -> str:
    """El prompt de siempre (sin IA o si la IA nombra lo que se dibuja)."""
    base = texto("una_foto", personaje=t.personaje, escenario=t.escenario)
    return f"{base} {texto('detras')}" if detras else base


def se_dibujan(prompt_: str, lugar: str, arte: Arte) -> list[str]:
    """D8: las palabras del prompt que el modelo dibujaría y que el lugar de Yael no trae."""
    p, lugar_ = prompt_.lower(), lugar.lower()
    return [
        palabra
        for palabra, permitidas in arte.se_dibujan.items()
        if palabra in p and not any(x in lugar_ for x in permitidas)
    ]


def referencias(carpeta: Path) -> list[Path]:
    return sorted(carpeta.glob("*.jpg"))


async def prompts_de_foto(
    llm: LLMProvider,
    i: ThumbnailInput,
    t: ImageTexts,
    bocetos: list[Path],
    refs: list[Path],
    arte: Arte,
) -> dict[str, str]:
    """S2: la IA de la nube escribe el prompt de cada plantilla mirando los bocetos y las
    miniaturas de referencia (solo la luz). Las imágenes las hace Z-Image (D1). Si un prompt
    nombra algo que se dibuja (D8), se pide de nuevo una vez; si insiste, va el fijo."""
    claves = list(arte.plantillas)
    pedido_ = texto(
        "ia_foto_pedido",
        personaje=i.figure_description,
        lugar=i.place_description,
        relacion=t.relacion or "-",
        plantillas=", ".join(claves),
    )
    imagenes = [boceto_para_la_ia(p) for p in [*bocetos, *refs]]
    salida = _salida_fotos(claves)
    fotos: dict[str, str] = {}
    malas: list[str] = []
    for intento in range(2):
        aviso = texto("ia_foto_reintento", palabras=", ".join(malas)) if malas else ""
        r, _ = await generate_structured(
            llm,
            role=ROLE,
            prompt=pedido_ + aviso,
            system_prompt=texto("ia_foto_sistema"),
            output=salida,
            images=imagenes,
        )
        malas = []
        for k in claves:
            if k in fotos:
                continue
            p = " ".join(getattr(r, k).prompt.split())
            dibujan = se_dibujan(p, i.place_description, arte)
            if dibujan and intento == 0:
                malas += dibujan
            elif not dibujan:
                fotos[k] = p
        if not malas:
            break
    escondida = t.a_medio_ver == "mucho"
    for k in claves:
        fotos.setdefault(k, foto_fija(t, escondida and k in arte.fundido.detras_en))
    return fotos
