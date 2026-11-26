"""H1a (Spec-800), cabeza de Yael: los ojos en Python para no tocar el tallado (Qwen-Edit lo
cambiaba). La cuenca entera, negra; en el centro, una pupila violeta más chica y más tenue."""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

AQUI = Path(__file__).resolve().parent
BASE = AQUI / "h1a/salidas/avatar_sola_s11.png"
SAL = AQUI / "h1a3/salidas"


def mascara(im: Image.Image, v_min: int) -> Image.Image:
    h, s, v = im.convert("HSV").split()
    m = ImageChops.multiply(
        h.point(lambda x: 255 if 175 < x < 230 else 0), s.point(lambda x: 255 if x > 60 else 0)
    )
    return ImageChops.multiply(m, v.point(lambda x: 255 if x > v_min else 0))


def solo_ojos(m: Image.Image, caja: tuple[int, int, int, int]) -> Image.Image:
    """Solo dentro de la caja de los ojos: el reflejo violeta del auricular no cuenta."""
    fuera = Image.new("L", m.size, 0)
    fuera.paste(m.crop(caja), caja[:2])
    return fuera


OJOS = (455, 135, 625, 200)  # la caja del brillo (470,151,610,187) con margen


def ojos(im: Image.Image, pupila: float, nucleo: int) -> Image.Image:
    cuenca = (
        solo_ojos(mascara(im, 60), OJOS)
        .filter(ImageFilter.MaxFilter(7))
        .filter(ImageFilter.GaussianBlur(2.5))
    )
    centro = solo_ojos(mascara(im, nucleo), OJOS).filter(ImageFilter.GaussianBlur(1.5))
    negro = ImageEnhance.Brightness(im).enhance(0.08)
    tenue = ImageEnhance.Brightness(im).enhance(pupila)
    sal = Image.composite(negro, im, cuenca)
    return Image.composite(tenue, sal, centro)


if __name__ == "__main__":
    SAL.mkdir(parents=True, exist_ok=True)
    im = Image.open(BASE).convert("RGB")
    for pupila, nucleo in ((0.7, 200),):
        d = SAL / f"ojos_py_{int(pupila * 100)}_{nucleo}.png"
        ojos(im, pupila, nucleo).save(d)
        print(d.name)
    sys.exit(0)
