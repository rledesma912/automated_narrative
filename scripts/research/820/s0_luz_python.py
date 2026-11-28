# Prueba P1 (solo Python): la misma composición con otra luz.
# Lo que ya era más claro en la nuestra (la niebla lejana) se vuelve niebla blanca;
# lo oscuro (troncos cercanos, la figura) queda en silueta. Gris azulado frío.
import sys

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

D = sys.argv[1]
OUT = sys.argv[2]
for t in ["A_der", "A_izq", "C_primer_plano", "B_lugar"]:
    img = Image.open(f"{D}/{t}_sin_color.png").convert("RGB")
    a = Image.open(f"{D}/{t}_alfa.png").convert("L")
    W, H = img.size
    L = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    grad = Image.linear_gradient("L").resize((W, H))
    vert = grad.point(
        lambda v: int(255 * max(0.25, min(1, 1.25 - (v / 255) ** 2 * 1.3)))
    )  # abajo (lo cercano) menos niebla
    lejos = L.filter(ImageFilter.GaussianBlur(40)).point(
        lambda v: int(255 * min(1, max(0, (v - 30) / 90)))
    )  # lo claro = lejos
    fogm = ImageChops.multiply(vert, lejos).point(lambda v: int(v * 0.85))
    fogm = ImageChops.multiply(fogm, ImageOps.invert(a.filter(ImageFilter.MaxFilter(5))))
    fog = Image.new("L", (W, H), 200)
    sil = L.point(lambda v: int(v * 0.55))
    bg = Image.composite(fog, sil, fogm)
    fig = img.convert("L").point(lambda v: min(55, int(v * 0.3)))
    out = Image.composite(fig, bg, a.filter(ImageFilter.GaussianBlur(1.5)))
    out = ImageOps.autocontrast(out, cutoff=(0.5, 0.2))
    col = ImageOps.colorize(out, black=(3, 5, 7), mid=(92, 104, 110), white=(226, 233, 237))
    ojos = ImageChops.multiply(a, img.convert("L").point(lambda v: 255 if v > 175 else 0)).filter(
        ImageFilter.GaussianBlur(2)
    )
    col = Image.composite(img, col, ojos)
    col = ImageEnhance.Sharpness(col).enhance(1.5)
    col.save(f"{OUT}/{t}.jpg", quality=90)
