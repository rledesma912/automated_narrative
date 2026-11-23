"""Spike C5b (Spec-790 D23): el tinte de la figura, como en la de Halloween de Yael.

Medido en la #5 (dW0nYhKpfqg): el personaje entero en naranja (S 142/255, tono ~15°) y el fondo
casi gris neutro (S 1). No es un acento: es un tinte en dos partes. Python sabe dónde está la
figura (su alfa en la composición), así que sin GPU:

  fondo    desaturado hasta `fondo_sat` (0 = gris neutro, como la #5; 40 = la mediana de C5)
  figura   tinte por luminancia (sombras → medios → luces del tono elegido) mezclado con la
           figura a `fuerza`; los acentos cálidos (la calabaza) quedan como estaban

Parte de las composiciones en color de C5 (`c5/salidas/comp/`); la figura se vuelve a ubicar con
las mismas reglas de C3 para tener su alfa.

    uv run python c5b_tinte.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c3_compositor as c3  # noqa: E402
import c5_color as c5  # noqa: E402
from comun import AQUI  # noqa: E402

SALIDAS = AQUI / "c5" / "salidas" / "tinte"
COMP = AQUI / "c5" / "salidas" / "comp"
CANAL = AQUI / "insumos" / "canal_yt"

# tonos: (sombras, medios, luces); van a arte.yaml si pasan
TONOS = {
    "naranja": ((18, 6, 2), (160, 72, 30), (255, 214, 170)),
    "rojo": ((20, 2, 2), (150, 30, 24), (255, 190, 175)),
    "frio": ((2, 10, 16), (50, 110, 130), (200, 235, 240)),
}
FUERZA = 0.85


def alfa_de(caso: str, plantilla: str) -> Image.Image:
    p = c3.PLANTILLAS[plantilla]
    fig = c3.figura_recortada(c5.SALIDAS / f"{caso}_recorte_s22.png", p["recorte"])
    f, pos = c3.ubicar(fig, p, c3.CASOS[caso]["apoyo"])
    return c3.alfa_en_cuadro(f, pos)


def tenir(im: Image.Image, alfa: Image.Image, tono: str, fondo_sat: float) -> Image.Image:
    fondo = c5.desaturar(im, fondo_sat) if fondo_sat > 0 else ImageOps.grayscale(im).convert("RGB")
    sombras, medios, luces = TONOS[tono]
    tenida = ImageOps.colorize(ImageOps.grayscale(im), black=sombras, mid=medios, white=luces)
    figura = Image.blend(im, tenida, FUERZA)
    acento = c5.acentos(im)
    figura = Image.composite(im, figura, acento)  # la calabaza queda como estaba
    m = alfa.filter(ImageFilter.GaussianBlur(2))
    return Image.composite(figura, fondo, m)


def main() -> None:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    variantes = [("naranja", 0), ("naranja", 40), ("rojo", 0), ("frio", 0)]
    for caso in c3.CASOS:
        cw, ch = 480, 270
        filas = []
        for pn in c3.PLANTILLAS:
            im = Image.open(COMP / f"{caso}_{pn}.png").convert("RGB")
            alfa = alfa_de(caso, pn)
            celdas = []
            for tono, fs in variantes:
                out = tenir(im, alfa, tono, fs)
                out.save(SALIDAS / f"{caso}_{pn}_{tono}_f{fs}.png")
                celdas.append((f"{tono}, fondo {'gris' if fs == 0 else fs}", out))
            filas.append((pn, celdas))
        real = Image.open(CANAL / f"{c3.CASOS[caso]['real']}.jpg").convert("RGB")
        o = Image.new("RGB", (cw * 5, (ch + 26) * len(filas) + 30), (18, 18, 18))
        d = ImageDraw.Draw(o)
        for r, (pn, celdas) in enumerate(filas):
            y = 30 + r * (ch + 26)
            d.text((6, y - 22), pn, fill=(255, 255, 0))
            fila = ([("Yael (real)", real)] if r == 0 else [("", None)]) + celdas
            for k, (rot, im) in enumerate(fila):
                if im is None:
                    continue
                o.paste(ImageOps.fit(im, (cw - 6, ch - 6)), (k * cw + 3, y))
                d.text((k * cw + 8, y + 4), rot, fill=(255, 255, 0))
        o.save(SALIDAS / f"hoja_{caso}.jpg", quality=90)
        print(SALIDAS / f"hoja_{caso}.jpg")


if __name__ == "__main__":
    main()
