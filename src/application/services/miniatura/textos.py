"""T3.3 (D27, D28): la IA separa lo que escribió Yael en el personaje solo, el lugar vacío y la
relación entre los dos, en inglés y en positivo. Los modelos de imagen dibujan todo lo que se
nombra y no entienden el «no» (cfg 1), así que nada crudo llega a ellos (E11c).
"""

from typing import Literal

from pydantic import BaseModel

from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.miniatura.arte import texto
from src.domain.interfaces import LLMProvider
from src.domain.thumbnail import ImageTexts, ThumbnailInput

ROLE = "miniatura"


class _Salida(BaseModel):
    personaje: str
    escenario: str
    relacion: str
    a_medio_ver: Literal["no", "poco", "mucho"]


def pedido(i: ThumbnailInput) -> str:
    return texto("ia_pedido", personaje=i.figure_description, lugar=i.place_description)


async def separar(llm: LLMProvider, i: ThumbnailInput, input_hash: str) -> ImageTexts:
    r, _ = await generate_structured(
        llm, role=ROLE, prompt=pedido(i), system_prompt=texto("ia_sistema"), output=_Salida
    )
    return ImageTexts(
        personaje=" ".join(r.personaje.split()),
        escenario=" ".join(r.escenario.split()),
        relacion=" ".join(r.relacion.split()),
        a_medio_ver=r.a_medio_ver,
        input_hash=input_hash,
    )
