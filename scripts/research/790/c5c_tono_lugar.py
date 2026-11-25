"""Spike C5c (Spec-790 D25): el tono sale del lugar, frío y desaturado, en TODA la imagen.

Python (sin GPU): escala de grises → tinte por luminancia hacia el tono del lugar, mezclado a
`fuerza` (que la saturación media quede cerca de la mediana de las recientes de Yael, 40/255).
Los acentos cálidos (velas, calabaza, ventana) quedan como estaban. Halloween = C5b.

    uv run python c5c_tono_lugar.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c3_compositor as c3  # noqa: E402
import c5_color as c5  # noqa: E402
from comun import AQUI  # noqa: E402

COMP = AQUI / "c5" / "salidas" / "comp"
SALIDAS = AQUI / "c5" / "salidas" / "tono"
CANAL = AQUI / "insumos" / "canal_yt"

# borrador de arte.yaml: tono → (sombras, medios, luces), fuerza, lugares
TONOS = {
    "verde": {"colores": ((4, 10, 6), (70, 92, 74), (205, 225, 208)), "fuerza": 0.55,
              "lugares": ["bosque", "campo", "selva", "monte", "maizal"]},
    "azul": {"colores": ((3, 6, 14), (62, 80, 108), (200, 214, 235)), "fuerza": 0.55,
             "lugares": ["mar", "lago", "río", "lluvia", "barco", "puerto"]},
    "gris_frio": {"colores": ((5, 7, 9), (80, 88, 94), (215, 222, 228)), "fuerza": 0.55,
                  "lugares": ["casa", "pueblo", "ruta", "ciudad", "hospital", "subte"]},
}


def entonar(im: Image.Image, tono: str) -> Image.Image:
    t = TONOS[tono]
    sombras, medios, luces = t["colores"]
    gris = ImageOps.grayscale(im)
    tenida = ImageOps.colorize(gris, black=sombras, mid=medios, white=luces)
    out = Image.blend(gris.convert("RGB"), tenida, t["fuerza"])
    return Image.composite(im, out, c5.acentos(im))


def main() -> None:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    ids = [line.strip() for line in (CANAL / "ids.txt").read_text().splitlines()]
    refs = {"verde": ids[2], "azul": ids[27], "gris_frio": ids[10]}  # #3 bosque, #28 mar, #11 casa
    cw, ch = 480, 270
    filas = []
    for caso in c3.CASOS:
        for pn in ("A_der", "B_lugar"):
            im = Image.open(COMP / f"{caso}_{pn}.png").convert("RGB")
            celdas = []
            for tono in TONOS:
                out = entonar(im, tono)
                out.save(SALIDAS / f"{caso}_{pn}_{tono}.png")
                celdas.append((f"{tono} (sat {c5.saturacion(out):.0f})", out))
            filas.append((f"{caso} {pn}", celdas))
    filas.insert(0, ("Yael: #3 bosque, #28 mar, #11 casa",
                     [(t, Image.open(CANAL / f"{refs[t]}.jpg").convert("RGB")) for t in TONOS]))
    o = Image.new("RGB", (cw * 3, (ch + 26) * len(filas) + 30), (18, 18, 18))
    d = ImageDraw.Draw(o)
    for r, (nombre, celdas) in enumerate(filas):
        y = 30 + r * (ch + 26)
        d.text((6, y - 22), nombre, fill=(255, 255, 0))
        for k, (rot, im) in enumerate(celdas):
            o.paste(ImageOps.fit(im, (cw - 6, ch - 6)), (k * cw + 3, y))
            d.text((k * cw + 8, y + 4), rot, fill=(255, 255, 0))
    o.save(SALIDAS / "hoja_tonos.jpg", quality=90)
    print(SALIDAS / "hoja_tonos.jpg")


if __name__ == "__main__":
    main()
