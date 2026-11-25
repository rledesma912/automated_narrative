"""Spike E6 (Spec-790 §10.0, rehecho después de C3/C5): la luz.

Lo que separa a las nuestras de las de Yael: ella tiene niebla iluminada, medios tonos y la figura
recortada contra algo claro; las nuestras son oscuras de punta a punta. Primero solo Python, sobre
las composiciones en color de C5 (con el alfa de la figura de C3):

  1. medios tonos   el FONDO (fuera del alfa) levanta sombras y medios (gamma)
  2. niebla         una capa gris clara, más densa abajo y en el horizonte
  3. zona clara     un halo de luz detrás de la figura (a la altura del pecho y la cabeza), solo
                    en el fondo: la figura queda recortada contra eso
  4. borde de luz   el contorno de la figura se aclara (contraluz)
  después           el tono del lugar (C5c) o el blanco y negro

Variantes: suave y fuerte. Mide el brillo medio contra las 36 recientes de Yael.

    uv run python e6_luz.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c3_compositor as c3  # noqa: E402
import c5c_tono_lugar as c5c  # noqa: E402
from c5b_tinte import alfa_de  # noqa: E402
from comun import AQUI  # noqa: E402
from e4_fundir import erosionar  # noqa: E402

COMP = AQUI / "c5" / "salidas" / "comp"
SALIDAS = AQUI / "e6" / "salidas"
CANAL = AQUI / "insumos" / "canal_yt"
W, H = 1280, 720

VARIANTES = {
    "suave": {"gamma": 0.80, "niebla": 0.16, "halo": 0.45, "borde": 0.55},
    "fuerte": {"gamma": 0.68, "niebla": 0.26, "halo": 0.75, "borde": 0.85},
}
NIEBLA = (175, 180, 182)
HALO = (225, 228, 230)


def brillo(im: Image.Image) -> float:
    return ImageStat.Stat(im.convert("L")).mean[0]


def gradiente_niebla() -> Image.Image:
    """Más niebla abajo (el piso) y una franja en el horizonte (~55 % del alto)."""
    g = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        abajo = max(0.0, (t - 0.55) / 0.45) ** 1.3
        horizonte = max(0.0, 1 - abs(t - 0.55) / 0.18) * 0.6
        g.putpixel((0, y), round(255 * min(1.0, abajo + horizonte + 0.25)))
    return g.resize((W, H))


def halo(alfa: Image.Image) -> Image.Image:
    x0, y0, x1, y1 = alfa.getbbox()
    cx, cy = (x0 + x1) / 2, y0 + 0.30 * (y1 - y0)
    r = 0.55 * H
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    pasos = 40
    for i in range(pasos, 0, -1):
        rr = r * i / pasos
        d.ellipse((cx - rr * 1.1, cy - rr, cx + rr * 1.1, cy + rr), fill=round(255 * (1 - i / pasos) ** 1.6))
    return m.filter(ImageFilter.GaussianBlur(30))


def iluminar(im: Image.Image, alfa: Image.Image, v: dict) -> Image.Image:
    duro = alfa.point(lambda x: 255 if x > 40 else 0)
    fuera = ImageChops.invert(duro).filter(ImageFilter.GaussianBlur(1.5))
    # 1. medios tonos del fondo
    lut = [round(255 * (x / 255) ** v["gamma"]) for x in range(256)]
    fondo = im.point(lut * 3)
    # 2. niebla
    capa = Image.new("RGB", (W, H), NIEBLA)
    fondo = Image.composite(capa, fondo, gradiente_niebla().point(lambda x: round(x * v["niebla"])))
    # 3. zona clara detrás de la figura (pantalla)
    luz = Image.new("RGB", (W, H), HALO)
    fondo = Image.composite(ImageChops.screen(fondo, luz), fondo, halo(alfa).point(lambda x: round(x * v["halo"])))
    out = Image.composite(fondo, im, fuera)
    # 4. borde de luz en la silueta
    borde = ImageChops.subtract(duro, erosionar(duro, 5)).filter(ImageFilter.GaussianBlur(3))
    borde = ImageChops.multiply(borde, alfa)
    out = Image.composite(ImageChops.screen(out, Image.new("RGB", (W, H), (205, 210, 215))), out,
                          borde.point(lambda x: round(x * v["borde"])))
    return out


def main() -> None:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    ids = [line.strip() for line in (CANAL / "ids.txt").read_text().splitlines()]
    yael = sorted(brillo(Image.open(CANAL / f"{i}.jpg")) for i in ids[:36])
    print(f"Yael, brillo medio de las 36 recientes: mediana {yael[18]:.0f}, p25 {yael[9]:.0f}, p75 {yael[27]:.0f}")
    tono = {"torre": "verde", "coneja": "gris_frio"}
    cw, ch = 480, 270
    filas = []
    for caso in c3.CASOS:
        real = Image.open(CANAL / f"{c3.CASOS[caso]['real']}.jpg").convert("RGB")
        for pn in c3.PLANTILLAS:
            im = Image.open(COMP / f"{caso}_{pn}.png").convert("RGB")
            alfa = alfa_de(caso, pn)
            celdas = [("antes", c5c.entonar(im, tono[caso]))]
            for vn, v in VARIANTES.items():
                out = c5c.entonar(iluminar(im, alfa, v), tono[caso])
                out.save(SALIDAS / f"{caso}_{pn}_{vn}.png")
                ImageOps.grayscale(iluminar(im, alfa, v)).save(SALIDAS / f"{caso}_{pn}_{vn}_byn.png")
                celdas.append((vn, out))
            celdas.append(("fuerte, ByN", Image.open(SALIDAS / f"{caso}_{pn}_fuerte_byn.png").convert("RGB")))
            if pn == "A_der":
                celdas.append(("Yael", real))
            filas.append((f"{caso} {pn}", celdas))
            print(caso, pn, " ".join(f"{r}:{brillo(i):.0f}" for r, i in celdas if r != "Yael"))
    o = Image.new("RGB", (cw * 5, (ch + 26) * len(filas) + 30), (18, 18, 18))
    d = ImageDraw.Draw(o)
    for r, (nombre, celdas) in enumerate(filas):
        y = 30 + r * (ch + 26)
        d.text((6, y - 22), nombre, fill=(255, 255, 0))
        for k, (rot, im) in enumerate(celdas):
            o.paste(ImageOps.fit(im, (cw - 6, ch - 6)), (k * cw + 3, y))
            d.text((k * cw + 8, y + 4), f"{rot} ({brillo(im):.0f})", fill=(255, 255, 0))
    o.save(SALIDAS / "hoja_luz.jpg", quality=88)
    print(SALIDAS / "hoja_luz.jpg")


if __name__ == "__main__":
    main()
