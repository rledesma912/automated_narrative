# ruff: noqa: N806, F841, B023  (spike: nombres de imagen en mayúscula, como en la 790)
"""Spec-820: Python controla al final (no pinta). Encuadre 1280×720, niveles (negro y blanco de
verdad), la niebla clara se lleva un poco más arriba y el color pasa a gris frío azulado."""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

from src.application.services.miniatura import imagen
from src.application.services.miniatura.arte import arte

GRIS_AZUL = [[3, 5, 8], [86, 98, 108], [222, 230, 237]]


def luz(im: Image.Image) -> dict:
    g = im.convert("L")
    h = g.histogram()
    n = sum(h)

    def pc(q):
        a = 0
        for i, v in enumerate(h):
            a += v
            if a >= n * q:
                return i

    return {"media": round(ImageStat.Stat(g).mean[0]), "p5": pc(0.05), "p95": pc(0.95)}


def controlar(im: Image.Image) -> Image.Image:
    A = arte()
    im = imagen.lienzo(im, A)
    im = ImageOps.autocontrast(im, cutoff=(1, 0.3), preserve_tone=True)
    L = im.convert("L")
    # la niebla: lo que ya es claro y difuso se aclara más (screen), lo oscuro no se toca
    m = L.filter(ImageFilter.GaussianBlur(30)).point(
        lambda v: int(255 * min(1, max(0, (v - 50) / 80)) * 0.7)
    )
    claro = ImageChops.screen(im, Image.new("RGB", im.size, (150, 158, 165)))
    im = Image.composite(claro, im, m)
    return imagen.entonar(imagen.desaturar(im, A.color.tope_desaturado), GRIS_AZUL, 0.6)


if __name__ == "__main__":
    for f in sys.argv[2:]:
        im = Image.open(f).convert("RGB")
        out = controlar(im)
        print(Path(f).name, "antes", luz(imagen.lienzo(im, arte())), "después", luz(out))
        out.save(Path(sys.argv[1]) / (Path(f).name.split("_profundidad")[0] + ".jpg"), quality=90)
