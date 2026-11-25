"""Spec-790 T6.5: la IA mira los bocetos al separar las descripciones (sin llamadas reales)."""

import io
import json

from PIL import Image

from src.application.services.miniatura import textos
from src.application.services.miniatura.arnes import Arnes
from src.domain.interfaces import LLMResponse
from src.domain.thumbnail import Thumbnail, ThumbnailInput
from tests.support.fake_comfy import FakeComfy

_SALIDA = {
    "personaje": "A tall pale creature",
    "escenario": "Tall pines in the fog",
    "relacion": "",
    "a_medio_ver": "no",
}


class _LLM:
    def __init__(self):
        self.llamadas: list[dict] = []

    async def generate(self, prompt, **kwargs):
        self.llamadas.append({"prompt": prompt, **kwargs})
        return LLMResponse(text=json.dumps(_SALIDA), provider="fake", model="fake")


def _png(ruta, color=(200, 200, 200), size=(400, 300), modo="RGB"):
    Image.new(modo, size, color).save(ruta, "PNG")


def _thumb(tmp_path) -> Thumbnail:
    _png(tmp_path / "personaje.png", (30, 30, 30))
    _png(tmp_path / "escenario.png", (220, 220, 220))
    return Thumbnail(
        story_id="s",
        input=ThumbnailInput(
            figure_description="Una criatura altísima.",
            place_description="Un bosque de pinos.",
            character_sketch="personaje.png",
            scene_sketch="escenario.png",
        ),
    )


async def test_manda_los_dos_bocetos_primero_el_personaje(tmp_path):
    llm = _LLM()
    arnes = Arnes(FakeComfy(), tmp_path, llm=llm)
    txt = await arnes.textos(_thumb(tmp_path))
    assert txt.escenario == "Tall pines in the fog"
    imagenes = llm.llamadas[0]["images"]
    assert [i.media_type for i in imagenes] == ["image/jpeg", "image/jpeg"]
    oscuro, claro = (Image.open(io.BytesIO(i.data)).getpixel((10, 10)) for i in imagenes)
    assert sum(oscuro) < sum(claro)  # el orden: personaje, después el lugar


async def test_cambiar_un_boceto_vuelve_a_leer(tmp_path):
    llm = _LLM()
    arnes = Arnes(FakeComfy(), tmp_path, llm=llm)
    thumb = _thumb(tmp_path)
    await arnes.textos(thumb)
    await arnes.textos(thumb)
    assert len(llm.llamadas) == 1  # nada cambió: se reusa
    _png(tmp_path / "escenario.png", (100, 180, 100))
    await arnes.textos(thumb)
    assert len(llm.llamadas) == 2


async def test_cambiar_la_descripcion_vuelve_a_leer(tmp_path):
    llm = _LLM()
    arnes = Arnes(FakeComfy(), tmp_path, llm=llm)
    thumb = _thumb(tmp_path)
    await arnes.textos(thumb)
    thumb.input.place_description = "Un cementerio."
    await arnes.textos(thumb)
    assert len(llm.llamadas) == 2


def test_el_boceto_se_achica_y_pierde_la_transparencia(tmp_path):
    ruta = tmp_path / "grande.png"
    _png(ruta, (0, 0, 0, 0), size=(4000, 2000), modo="RGBA")
    img = textos.boceto_para_la_ia(ruta)
    im = Image.open(io.BytesIO(img.data))
    assert im.format == "JPEG" and max(im.size) == textos.LADO_MAX
    assert im.getpixel((5, 5)) == (255, 255, 255)  # lo transparente es papel blanco


def test_el_prompt_de_sistema_habla_de_los_bocetos():
    from src.application.services.miniatura.arte import texto

    sistema = texto("ia_sistema")
    assert "bocetos" in sistema and "primero el del personaje" in sistema


def test_el_fundido_de_escondido_esta_en_positivo_y_pide_que_asome():
    from src.application.services.miniatura.arte import prompt

    p = prompt("fundir_detras")
    assert "in front of" in p and "peeks out" in p
