"""H1a (Spec-800), cabeza de Yael: después de cambiar la ropa (Qwen-Edit), la cabeza vuelve a ser
la original. Como el fundido de las miniaturas pero al revés: lo que entra de la imagen original
es la cabeza (la calabaza y los auriculares), con el borde difuminado y la exposición igualada en
el anillo de alrededor. Lo que tapa la cara por delante (la mano con el micrófono) queda de la
ropa nueva: solo entra lo naranja de la calabaza en la mitad de abajo de la cabeza.

    uv run python scripts/research/800/h1a3_cabeza.py <cabeza.png> <ropa_*.png ...>
"""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


def naranja(im: Image.Image) -> Image.Image:
    h, s, v = im.convert("HSV").split()
    m = ImageChops.multiply(
        h.point(lambda x: 255 if 8 < x < 32 else 0), s.point(lambda x: 255 if x > 90 else 0)
    )
    return ImageChops.multiply(m, v.point(lambda x: 255 if x > 50 else 0))


ARRIBA = 330  # la cabeza está arriba de esta línea; abajo hay botas y cuero del mismo tono


def mascara_cabeza(cab: Image.Image) -> Image.Image:
    cal = naranja(cab).filter(ImageFilter.MedianFilter(5))
    tapa = Image.new("L", cab.size, 0)
    tapa.paste(255, (0, 0, cab.width, ARRIBA))
    cal = ImageChops.multiply(cal, tapa)
    # la calabaza y, alrededor, los auriculares: todo lo que no es el gris liso del fondo
    cerca = cal.filter(ImageFilter.MaxFilter(41))
    _, sat, val = cab.convert("HSV").split()
    fondo = ImageChops.multiply(
        sat.point(lambda x: 255 if x < 30 else 0), val.point(lambda x: 255 if 95 < x < 175 else 0)
    )
    m = ImageChops.multiply(cerca, ImageChops.invert(fondo.filter(ImageFilter.MinFilter(3))))
    return m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(2))


def proteger(cab: Image.Image, nueva: Image.Image) -> Image.Image:
    nueva = nueva.convert("RGB").resize(cab.size, Image.Resampling.LANCZOS)
    m = mascara_cabeza(cab)
    return Image.composite(cab, nueva, m)  # misma luz de estudio: sin igualar (dejaba un halo)


if __name__ == "__main__":
    cab = Image.open(sys.argv[1]).convert("RGB")
    for r in sys.argv[2:]:
        p = Path(r)
        d = p.with_name(p.stem + "_cabeza.png")
        proteger(cab, Image.open(p)).save(d)
        print(d.name)
