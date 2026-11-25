"""Spike C5 (Spec-790 D23): color desaturado o blanco y negro.

Las piezas se generan SIEMPRE en color desaturado; el blanco y negro lo hace Python al final.
Mismo camino que E1 + E2 + E3c, con los prompts cambiados de «black and white» a color desaturado
con tinte frío, y los acentos cálidos solo donde hay una luz real (una vela, la calabaza, los ojos):

  personaje   boceto → Qwen-Edit 2511 (prompt de E1 en color) → BiRefNet → recorte
  escenario   boceto → Qwen-Edit 2511 (prompt de E3 en color) → curva de oscuridad en Python →
              Z-Image img2img 0,45 (prompt de E3c en color)
  componer    las 4 plantillas de C3, SIN título (D22), con el fundido de E4
  color       «desaturado»: Python baja la saturación media (de lo que no es negro) hasta la
              mediana de las 36 recientes de Yael (40/255) si la pasa; «byn»: escala de grises

    uv run python c5_color.py [--semillas 11,22] [--semilla-comp 22] [--solo-hoja]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c3_compositor as c3  # noqa: E402
from comun import AQUI, INSUMOS, Comfy  # noqa: E402
from e1_personaje import BOCETOS as PERSONAJES  # noqa: E402
from e1_personaje import FONDO, grafo_qwen, grafo_zimage  # noqa: E402
from e2_recortar import grafo_birefnet, recorte  # noqa: E402
from e3c_oscuro import BOCETOS as LUGARES  # noqa: E402
from e3c_oscuro import curva  # noqa: E402

SALIDAS = AQUI / "c5" / "salidas"
CANAL = AQUI / "insumos" / "canal_yt"
SAT_YAEL = 40  # mediana de la saturación media (V > 40) de las 36 recientes

COLOR = (
    "Dark horror night photograph, photorealistic, muted desaturated colors with a cold "
    "blue-teal night tint, cinematic, looks like a real photo taken at night, not a painting, "
    "not a cartoon. Only a real light source that is already in the description keeps a warm "
    "color."
)
LUZ = "A single hard light source, deep crushed blacks, the figure partly lit and partly in shadow."
TEXTURA = "Heavy film grain, dirty scratched texture."
VACIO = "Nobody in the scene: no people, no creatures, no animals."

OSCURO_COLOR = (
    "A real, unedited photograph taken on a very dark night with a full-frame camera and a "
    "35mm lens, in muted desaturated colors with a cold blue-teal night tint, underexposed. "
    "Almost no light: only a faint, diffuse moonglow coming through thick fog. No lamps, no "
    "lit windows, no glowing lights, no bright moon. Dense fog fills the scene and swallows "
    "the distance; most of the image is in deep darkness, shapes barely visible. Realistic "
    "materials and textures: weathered wood, old stone, real roof tiles, real pine needles and "
    "bark, real grass and dirt. Natural film grain. It must look like a real place "
    "photographed by a person: not an illustration, not a drawing, not a cartoon, not a 3D "
    "render, not CGI, not stylized. Nobody in the scene: no people, no creatures, no animals. "
    "Nothing else besides what is described: no extra objects."
)

CASOS = {
    "torre": {"personaje": "torre_piel", "lugar": "torre"},
    "coneja": {"personaje": "mansion", "lugar": "mansion"},
}
BOCETO_LUGAR = {"torre": "torre_escenario.png", "mansion": "mansion_escenario.png"}


def prompt_personaje(desc: str) -> str:
    return (
        "Turn this rough pencil sketch into a finished image of the same character, keeping "
        "exactly the pose, the proportions, the silhouette and the position in the frame of "
        f"the sketch. {desc} {COLOR} {LUZ} {TEXTURA} {FONDO} No pencil lines, no text."
    )


def prompt_lugar(desc: str) -> str:
    return (
        "Turn this rough pencil sketch into a finished image of the same place, keeping "
        "exactly the composition, the perspective, the layout and the position and size of "
        f"every element of the sketch. {desc} {COLOR} Cold damp night air, low fog close to the "
        f"ground. {TEXTURA} {VACIO} No pencil lines, no text."
    )


# ── color (Python) ───────────────────────────────────────────────────────────────
def saturacion(im: Image.Image) -> float:
    h, s, v = im.convert("HSV").split()
    m = v.point(lambda x: 255 if x > 40 else 0)
    return ImageStat.Stat(s, m).mean[0] if m.getbbox() else 0.0


def acentos(im: Image.Image) -> Image.Image:
    """Las luces cálidas reales (llama, calabaza encendida, ventana): tono rojo-naranja-amarillo,
    saturado y brillante. Máscara suave."""
    h, s, v = im.convert("HSV").split()
    calido = h.point(lambda x: 255 if (x <= 32 or x >= 240) else 0)
    m = ImageChops.multiply(calido, s.point(lambda x: 255 if x > 90 else 0))
    m = ImageChops.multiply(m, v.point(lambda x: 255 if x > 80 else 0))
    return m.filter(ImageFilter.GaussianBlur(2))


def desaturar(im: Image.Image, tope: float = SAT_YAEL) -> Image.Image:
    """Baja la saturación de todo MENOS los acentos cálidos (como Yael: el resto apagado y la
    calabaza o la vela encendidas), hasta la mediana de sus recientes."""
    m = acentos(im)
    h, s, v = im.convert("HSV").split()
    fuera = ImageChops.invert(m).point(lambda x: 255 if x > 128 else 0)
    vlum = v.point(lambda x: 255 if x > 40 else 0)
    ref = ImageChops.multiply(fuera, vlum)
    sat = ImageStat.Stat(s, ref).mean[0] if ref.getbbox() else 0
    k = min(1.0, tope / sat) if sat else 1.0
    bajo = Image.merge("HSV", (h, s.point(lambda x: round(x * k)), v)).convert("RGB")
    return Image.composite(im, bajo, m)


def byn(im: Image.Image) -> Image.Image:
    return ImageOps.grayscale(im).convert("RGB")


# ── la corrida ───────────────────────────────────────────────────────────────────
async def piezas(semillas: list[int]) -> dict:
    medidas: dict = {}
    async with Comfy() as c:
        await c.liberar()
        for caso, d in CASOS.items():
            p, lugar = d["personaje"], d["lugar"]
            sub_p = await c.subir(INSUMOS / "bocetos" / PERSONAJES[p]["archivo"])
            sub_l = await c.subir(INSUMOS / "bocetos" / BOCETO_LUGAR[lugar])
            for s in semillas:
                # personaje
                crudo = SALIDAS / f"{caso}_personaje_s{s}.png"
                r = await c.correr(grafo_qwen(sub_p, prompt_personaje(PERSONAJES[p]["descripcion"]), s, f"spec790/c5/{caso}_p_s{s}"))
                await c.bajar(r.imagenes[0], crudo)
                medidas[f"{caso}_personaje_s{s}"] = r.segundos
                r = await c.correr(grafo_birefnet(await c.subir(crudo), f"spec790/c5/{caso}_m_s{s}"))
                masc = SALIDAS / f"{caso}_mascara_s{s}.png"
                await c.bajar(r.imagenes[0], masc)
                recorte(crudo, Image.open(masc).convert("L"), SALIDAS / f"{caso}_recorte_s{s}.png")
                # escenario
                q = SALIDAS / f"{caso}_escenario_qwen_s{s}.png"
                r = await c.correr(grafo_qwen(sub_l, prompt_lugar(LUGARES[lugar]), s, f"spec790/c5/{caso}_lq_s{s}"))
                await c.bajar(r.imagenes[0], q)
                previa = curva(q, SALIDAS / f"{caso}_escenario_oscurecido_s{s}.png")
                r = await c.correr(grafo_zimage(f"{OSCURO_COLOR} {LUGARES[lugar]}", s, f"spec790/c5/{caso}_lz_s{s}",
                                                await c.subir(previa), 0.45))
                await c.bajar(r.imagenes[0], SALIDAS / f"{caso}_escenario_s{s}.png")
                medidas[f"{caso}_escenario_s{s}"] = r.segundos
                print(caso, s, "piezas listas", flush=True)
        await c.liberar()
    return medidas


async def componer(semilla: int) -> None:
    # el compositor de C3, con las piezas en color y sin título
    c3.SALIDAS = SALIDAS / "comp"
    c3.SALIDAS.mkdir(parents=True, exist_ok=True)
    for caso in c3.CASOS:
        c3.CASOS[caso]["escena"] = SALIDAS / f"{caso}_escenario_s{semilla}.png"
        c3.CASOS[caso]["figura"] = SALIDAS / f"{caso}_recorte_s{semilla}.png"
    await c3.main(semilla, con_qwen=True, con_titulo=False)
    for caso in c3.CASOS:
        for pn in c3.PLANTILLAS:
            im = Image.open(c3.SALIDAS / f"{caso}_{pn}.png").convert("RGB")
            desaturar(im).save(SALIDAS / f"{caso}_{pn}_desaturado.png")  # noqa
            byn(im).save(SALIDAS / f"{caso}_{pn}_byn.png")


def hojas(semillas: list[int]) -> None:
    for caso, d in CASOS.items():
        cw, ch = 480, 270
        cols = 5
        o = Image.new("RGB", (cw * cols, (ch + 26) * 3 + 30), (18, 18, 18))
        dd = ImageDraw.Draw(o)
        real = Image.open(CANAL / f"{c3.CASOS[caso]['real']}.jpg").convert("RGB")
        filas = [("desaturado", [("Yael (real)", real)] + [
                     (pn, Image.open(SALIDAS / f"{caso}_{pn}_desaturado.png")) for pn in c3.PLANTILLAS]),
                 ("blanco y negro", [("Yael en ByN", byn(real))] + [
                     (pn, Image.open(SALIDAS / f"{caso}_{pn}_byn.png")) for pn in c3.PLANTILLAS]),
                 ("piezas", [(f"personaje s{s}", Image.open(SALIDAS / f"{caso}_personaje_s{s}.png")) for s in semillas]
                  + [(f"escenario s{s}", Image.open(SALIDAS / f"{caso}_escenario_s{s}.png")) for s in semillas])]
        for r, (nombre, celdas) in enumerate(filas):
            y = 30 + r * (ch + 26)
            dd.text((6, y - 22), nombre, fill=(255, 255, 0))
            for k, (rot, im) in enumerate(celdas[:cols]):
                o.paste(ImageOps.fit(im.convert("RGB"), (cw - 6, ch - 6)), (k * cw + 3, y))
                dd.text((k * cw + 8, y + 4), rot, fill=(255, 255, 0))
        o.save(SALIDAS / f"hoja_{caso}.jpg", quality=90)
        print(SALIDAS / f"hoja_{caso}.jpg")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--semillas", default="11,22")
    ap.add_argument("--semilla-comp", type=int, default=22)
    ap.add_argument("--solo-hoja", action="store_true")
    a = ap.parse_args()
    sem = [int(x) for x in a.semillas.split(",")]
    SALIDAS.mkdir(parents=True, exist_ok=True)
    if not a.solo_hoja:
        m = asyncio.run(piezas(sem))
        (SALIDAS / "medidas.json").write_text(json.dumps(m, indent=2))
        asyncio.run(componer(a.semilla_comp))
    hojas(sem)
