"""Spec-820 S2: los prompts de la foto única que escribe la IA (sin LLM ni GPU)."""

from pathlib import Path

from PIL import Image

from src.application.services.miniatura import textos
from src.application.services.miniatura.arte import arte
from src.domain.thumbnail import ImageTexts, ThumbnailInput

_TXT = ImageTexts(
    personaje="A tall furry creature.", escenario="A misty forest.", a_medio_ver="mucho"
)
_IN = ThumbnailInput(figure_description="Una criatura.", place_description="Un bosque con niebla.")


def _bocetos(tmp_path: Path) -> list[Path]:
    rutas = []
    for n in ("personaje", "escenario"):
        p = tmp_path / f"{n}.png"
        Image.new("RGB", (64, 64), (128, 128, 128)).save(p)
        rutas.append(p)
    return rutas


def _respuestas(monkeypatch, *tandas: dict[str, str]):
    """`generate_structured` de mentira: cada llamada devuelve la tanda siguiente."""
    pedidos: list[str] = []
    seguir = iter(tandas)

    async def falso(_llm, *, role, prompt, system_prompt, output, images):  # noqa: ARG001
        pedidos.append(prompt)
        assert role == "miniatura" and len(images) == 2 + 1
        tanda = next(seguir)
        return output(**{k: {"prompt": v, "luz": "contraluz"} for k, v in tanda.items()}), None

    monkeypatch.setattr(textos, "generate_structured", falso)
    return pedidos


def _todas(p: str) -> dict[str, str]:
    return {k: p for k in arte().plantillas}


def test_la_foto_fija_suma_el_tronco_solo_si_esta_detras():
    sin = textos.foto_fija(_TXT, detras=False)
    con = textos.foto_fija(_TXT, detras=True)
    assert "A tall furry creature." in sin and "A misty forest." in sin
    assert "trunk" in con and con.startswith(sin)


def test_lo_que_se_dibuja_salvo_que_el_lugar_lo_traiga():  # D8
    a = arte()
    assert textos.se_dibujan("a camera on a tripod, 35mm", "un bosque", a) == ["camera", "tripod"]
    assert textos.se_dibujan("under the moon", "un bosque", a) == ["moon"]
    assert textos.se_dibujan("under the moon", "un bosque bajo la luna", a) == []


async def test_la_ia_escribe_un_prompt_por_plantilla(monkeypatch, tmp_path):
    ref = tmp_path / "ref.jpg"
    Image.new("RGB", (64, 36)).save(ref)
    pedidos = _respuestas(monkeypatch, _todas("Backlit   creature,  matte fur."))
    fotos = await textos.prompts_de_foto(None, _IN, _TXT, _bocetos(tmp_path), [ref], arte())
    assert fotos == _todas("Backlit creature, matte fur.")
    assert len(pedidos) == 1 and "Un bosque con niebla." in pedidos[0]


async def test_si_nombra_lo_que_se_dibuja_se_pide_de_nuevo_y_si_insiste_va_la_fija(
    monkeypatch, tmp_path
):
    ref = tmp_path / "ref.jpg"
    Image.new("RGB", (64, 36)).save(ref)
    primera = _todas("Backlit creature.") | {"C_primer_plano": "A camera two meters away."}
    segunda = _todas("Backlit creature.") | {"C_primer_plano": "Still a camera."}
    pedidos = _respuestas(monkeypatch, primera, segunda)
    fotos = await textos.prompts_de_foto(None, _IN, _TXT, _bocetos(tmp_path), [ref], arte())
    assert len(pedidos) == 2 and "camera" in pedidos[1]  # el aviso del reintento
    assert fotos["A_der"] == "Backlit creature."
    assert fotos["C_primer_plano"] == textos.foto_fija(_TXT, detras=False)


def test_la_guia_de_la_ia_pide_materiales_mate_y_no_nombrar_la_camara():
    from src.application.services.miniatura.arte import texto

    guia = texto("ia_foto_sistema")
    for seccion in ("mate", "plumón", "pelo", "nunca nombres la cámara", "solo para leer la luz"):
        assert seccion in guia, seccion
    for clave in arte().plantillas:
        assert clave in guia, clave


def test_la_foto_fija_va_en_positivo():  # D27
    import re

    assert not re.search(
        r"\b(no|not|without|nobody|never)\b", textos.foto_fija(_TXT, detras=True), re.I
    )


def test_la_palabra_halo_no_puede_ir_en_un_prompt():  # tanda 17: dibujó un aro de ángel
    assert textos.se_dibujan("a thin halo of fog", "un bosque", arte()) == ["halo"]
    assert "halo" not in textos.foto_fija(_TXT, detras=True).lower()
