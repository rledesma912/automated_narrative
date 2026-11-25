"""Lo que hace Python con las imágenes (Spec-790 D15: ComfyUI hace una sola cosa por llamada;
el resto, acá). Puro Pillow, sin GPU. Sale de los spikes E3c, E4 (ronda 2), C3, C5 y C5c.
"""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

from src.application.services.miniatura.arte import Arte, Plantilla


# ── básicos ─────────────────────────────────────────────────────────────────────
def dilatar(m: Image.Image, radio: int) -> Image.Image:
    while radio > 0:
        paso = min(radio, 4)
        m = m.filter(ImageFilter.MaxFilter(paso * 2 + 1))
        radio -= paso
    return m


def erosionar(m: Image.Image, radio: int) -> Image.Image:
    while radio > 0:
        paso = min(radio, 4)
        m = m.filter(ImageFilter.MinFilter(paso * 2 + 1))
        radio -= paso
    return m


def anillo(m: Image.Image, ancho: int) -> Image.Image:
    return ImageChops.subtract(dilatar(m, ancho), m)


def lum(img: Image.Image, m: Image.Image | None = None) -> float:
    return ImageStat.Stat(img.convert("L"), m).mean[0]


def cuanto(m: Image.Image, area: Image.Image) -> float:
    """Fracción de `area` (0–255) que cae dentro de `m`."""
    inter = ImageChops.multiply(m, area).histogram()
    tot = area.histogram()
    s_tot = sum(i * c for i, c in enumerate(tot))
    return sum(i * c for i, c in enumerate(inter)) / 255 / s_tot if s_tot else 0.0


# ── escenario (E3c) ───────────────────────────────────────────────────────────────
def oscurecer_escenario(im: Image.Image, arte: Arte) -> Image.Image:
    """La curva antes de «fotografiarlo»: medios tonos hacia abajo y luces recortadas."""
    g, t = arte.escenario.gamma, arte.escenario.techo
    lut = [round(255 * t * (v / 255) ** g) for v in range(256)]
    return im.convert("RGB").point(lut * 3)


def lienzo(im: Image.Image, arte: Arte, espejo: bool = False) -> Image.Image:
    out = ImageOps.fit(
        im.convert("RGB"), (arte.lienzo.ancho, arte.lienzo.alto), Image.Resampling.LANCZOS
    )
    return ImageOps.mirror(out) if espejo else out


# ── recorte (E2) ──────────────────────────────────────────────────────────────────
def con_alfa(im: Image.Image, mascara: Image.Image) -> Image.Image:
    rgba = im.convert("RGB").copy()
    rgba.putalpha(mascara.convert("L").resize(im.size))
    return rgba


# ── la figura en el cuadro (C3) ───────────────────────────────────────────────────
def figura_recortada(fig: Image.Image, recorte: float) -> Image.Image:
    f = fig.convert("RGBA")
    caja = f.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if caja:
        f = f.crop(caja)
    if recorte < 1:
        f = f.crop((0, 0, f.width, round(f.height * recorte)))
    return f


def apoyo(fig: Image.Image) -> str:
    """«borde» si la figura llega cortada abajo (de la cintura para arriba); si no, «piso»."""
    a = fig.convert("RGBA").getchannel("A")
    caja = a.point(lambda v: 255 if v > 8 else 0).getbbox()
    if not caja:
        return "piso"
    a = a.crop(caja)
    fila = a.crop((0, a.height - 4, a.width, a.height)).point(lambda v: 255 if v > 32 else 0)
    lleno = fila.histogram()[255] / (fila.width * fila.height)
    # cortada a la cintura: la última fila está llena; parada: solo los pies
    return "borde" if lleno > 0.40 else "piso"


def ubicar(
    fig: Image.Image, p: Plantilla, apoyo_: str, arte: Arte
) -> tuple[Image.Image, tuple[int, int]]:
    ancho_c, alto_c = arte.lienzo.ancho, arte.lienzo.alto
    escala = p.alto * alto_c / fig.height
    f = fig.resize(
        (max(1, round(fig.width * escala)), max(1, round(fig.height * escala))),
        Image.Resampling.LANCZOS,
    )
    x = round(p.cx * ancho_c - f.width / 2)
    if p.recorte < 1 or apoyo_ == "borde":
        y = alto_c - f.height + (round(0.04 * alto_c) if p.recorte < 1 else 0)
    elif p.alto < 0.7:
        y = round(0.86 * alto_c - f.height)
    else:
        y = round(0.98 * alto_c - f.height)
    return f, (x, y)


def alfa_en_cuadro(f: Image.Image, pos: tuple[int, int], arte: Arte) -> Image.Image:
    a = Image.new("L", (arte.lienzo.ancho, arte.lienzo.alto), 0)
    a.paste(f.getchannel("A"), pos)
    return a


def oscurecer_figura(
    f: Image.Image, fondo: Image.Image, alfa: Image.Image, arte: Arte
) -> Image.Image:
    """E4 ronda 2: la figura hasta la luz del lugar (gamma con techo), con grano."""
    fa = arte.figura
    duro = alfa.point(lambda v: 255 if v > 128 else 0)
    media_lugar = lum(fondo, anillo(duro, round(fa.anillo * arte.lienzo.alto)))
    rgb = f.convert("RGB")
    duro_fig = f.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    media_fig = lum(rgb, duro_fig)
    objetivo = min(max(fa.veces_el_lugar * media_lugar, fa.piso), media_fig)
    lo, hi = 0.3, 6.0
    tabla = list(range(256))
    for _ in range(25):
        k = (lo + hi) / 2
        tabla = [round(255 * fa.techo * (v / 255) ** k) for v in range(256)]
        if lum(rgb.point(tabla * 3), duro_fig) > objetivo:
            lo = k
        else:
            hi = k
    original = rgb
    rgb = rgb.point(tabla * 3)
    # las luces cálidas que trae la figura (una calabaza encendida, una vela) no se apagan
    rgb = Image.composite(original, rgb, acentos(original))
    if fa.grano > 0:
        rgb = ImageChops.add(rgb, Image.effect_noise(rgb.size, fa.grano).convert("RGB"), 1.0, -128)
    out = rgb.convert("RGBA")
    out.putalpha(f.getchannel("A").filter(ImageFilter.GaussianBlur(1.2)))
    return out


def componer(
    fondo: Image.Image, f: Image.Image, pos, apoyo_: str, p: Plantilla, arte: Arte
) -> Image.Image:
    ancho_c, alto_c = arte.lienzo.ancho, arte.lienzo.alto
    comp = fondo.copy()
    if apoyo_ == "piso" and p.recorte == 1:
        x, y = pos
        sombra = Image.new("L", (ancho_c, alto_c), 0)
        cx, y1 = x + f.width / 2, y + f.height
        ImageDraw.Draw(sombra).ellipse(
            (cx - 0.5 * f.width, y1 - 0.03 * alto_c, cx + 0.55 * f.width, y1 + 0.02 * alto_c),
            fill=190,
        )
        comp = Image.composite(
            Image.new("RGB", (ancho_c, alto_c)),
            comp,
            sombra.filter(ImageFilter.GaussianBlur(0.012 * alto_c)),
        )
    comp.paste(f, pos, f)
    return comp


def espejo_conviene(alfa: Image.Image, importante: Image.Image | None) -> bool:
    """C3: si la figura taparía lo importante del escenario, espejarlo."""
    if importante is None:
        return False
    imp = importante.convert("L").resize(alfa.size).point(lambda v: 255 if v > 128 else 0)
    return cuanto(alfa, ImageOps.mirror(imp)) < cuanto(alfa, imp)


# ── el fundido (E4 ronda 2) ───────────────────────────────────────────────────────
def mascara_fundir(alfa: Image.Image, arte: Arte) -> Image.Image:
    return dilatar(
        alfa.point(lambda v: 255 if v > 32 else 0),
        round(arte.fundido.dilatacion * arte.lienzo.alto),
    )


def zona(m: Image.Image, arte: Arte) -> tuple[int, int, int, int]:
    ancho_c, alto_c = arte.lienzo.ancho, arte.lienzo.alto
    x0, y0, x1, y1 = m.getbbox() or (0, 0, ancho_c, alto_c)
    mg = round(arte.fundido.margen * alto_c)
    return max(0, x0 - mg), max(0, y0 - mg), min(ancho_c, x1 + mg), min(alto_c, y1 + mg)


def igualar(editado: Image.Image, original: Image.Image, ref: Image.Image) -> Image.Image:
    """Media y desvío de cada canal de `editado` a los de `original`, medidos en `ref`."""
    if not ref.getbbox():
        return editado
    se, so = ImageStat.Stat(editado, ref), ImageStat.Stat(original, ref)
    tablas: list[int] = []
    for c in range(3):
        ke = so.stddev[c] / max(se.stddev[c], 1)
        tablas += [max(0, min(255, round((v - se.mean[c]) * ke + so.mean[c]))) for v in range(256)]
    return editado.point(tablas)


def pegar_fundido(
    comp: Image.Image, editado: Image.Image, caja, m: Image.Image, arte: Arte
) -> Image.Image:
    """Lo editado entra solo dentro de la máscara, con el borde difuminado hacia adentro."""
    x0, y0, x1, y1 = caja
    ed_zona = editado.convert("RGB").resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    m_zona = m.crop(caja)
    ed_zona = igualar(
        ed_zona, comp.crop(caja), anillo(m_zona, round(arte.figura.anillo * arte.lienzo.alto))
    )
    ed = comp.copy()
    ed.paste(ed_zona, (x0, y0))
    b = arte.fundido.borde
    suave = ImageChops.multiply(erosionar(m, b).filter(ImageFilter.GaussianBlur(b / 2)), m)
    return Image.composite(ed, comp, suave)


# ── el color (C5, C5b, C5c) ───────────────────────────────────────────────────────
def saturacion(im: Image.Image) -> float:
    _, s, v = im.convert("HSV").split()
    m = v.point(lambda x: 255 if x > 40 else 0)
    return ImageStat.Stat(s, m).mean[0] if m.getbbox() else 0.0


def acentos(im: Image.Image) -> Image.Image:
    """Las luces cálidas reales (llama, calabaza encendida): rojo-naranja, saturado y brillante.
    T6.4: también el amarillo muy brillante (ojos que brillan)."""
    return ImageChops.lighter(_calidos(im, 0, 32, 80), _calidos(im, 33, 45, 150)).filter(
        ImageFilter.GaussianBlur(2)
    )


def _calidos(im: Image.Image, h0: int, h1: int, brillo: int) -> Image.Image:
    h, s, v = im.convert("HSV").split()
    tono = h.point(lambda x: 255 if (h0 <= x <= h1 or (h0 == 0 and x >= 240)) else 0)
    m = ImageChops.multiply(tono, s.point(lambda x: 255 if x > 90 else 0))
    return ImageChops.multiply(m, v.point(lambda x: 255 if x > brillo else 0))


def restaurar_luces(antes: Image.Image, despues: Image.Image) -> Image.Image:
    """T6.4: el fundido de Qwen cambia el tono de las luces (ojos amarillos → verdosos) y el
    color después las apaga. Las luces muy brillantes se toman de antes del fundido."""
    luces = ImageChops.lighter(_calidos(antes, 0, 32, 150), _calidos(antes, 33, 45, 150))
    return Image.composite(antes, despues, luces.filter(ImageFilter.GaussianBlur(2)))


def a_medio_ver(
    final: Image.Image, fondo: Image.Image, alfa: Image.Image, nivel: str, arte: Arte
) -> Image.Image:
    """T6.4: de la cintura para abajo la figura se pierde en la sombra del lugar (no se vuelve
    transparente: se verían los árboles a través)."""
    mv = arte.figura.medio_ver.get(nivel)
    caja = alfa.point(lambda v: 255 if v > 32 else 0).getbbox()
    if mv is None or caja is None:
        return final
    x0, y0, x1, y1 = caja
    tabla = [
        0
        if t / 255 < mv.desde
        else round(255 * (1 - mv.queda) * min(1, (t / 255 - mv.desde) / (1 - mv.desde)) ** 1.3)
        for t in range(256)
    ]
    rampa = Image.new("L", final.size, 0)
    rampa.paste(Image.linear_gradient("L").resize((x1 - x0, y1 - y0)).point(tabla), (x0, y0))
    sombra = fondo.convert("RGB").point(lambda v: round(v * arte.figura.sombra))
    return Image.composite(sombra, final, ImageChops.multiply(rampa, alfa))


def desaturar(im: Image.Image, tope: float) -> Image.Image:
    m = acentos(im)
    h, s, v = im.convert("HSV").split()
    ref = ImageChops.multiply(
        ImageChops.invert(m).point(lambda x: 255 if x > 128 else 0),
        v.point(lambda x: 255 if x > 40 else 0),
    )
    sat = ImageStat.Stat(s, ref).mean[0] if ref.getbbox() else 0
    k = min(1.0, tope / sat) if sat else 1.0
    bajo = Image.merge("HSV", (h, s.point(lambda x: round(x * k)), v)).convert("RGB")
    return Image.composite(im, bajo, m)


def entonar(im: Image.Image, colores, fuerza: float) -> Image.Image:
    sombras, medios, luces = (tuple(c) for c in colores)
    gris = ImageOps.grayscale(im)
    tenida = ImageOps.colorize(gris, black=sombras, mid=medios, white=luces)
    out = Image.blend(gris.convert("RGB"), tenida, fuerza)
    return Image.composite(im.convert("RGB"), out, acentos(im))


def tenir_figura(im: Image.Image, alfa: Image.Image, colores, fuerza: float) -> Image.Image:
    """Halloween (C5b): la figura en el tono, el fondo gris, los acentos tal cual."""
    fondo = ImageOps.grayscale(im).convert("RGB")
    sombras, medios, luces = (tuple(c) for c in colores)
    tenida = ImageOps.colorize(ImageOps.grayscale(im), black=sombras, mid=medios, white=luces)
    figura = Image.blend(im.convert("RGB"), tenida, fuerza)
    figura = Image.composite(im.convert("RGB"), figura, acentos(im))
    return Image.composite(figura, fondo, alfa.filter(ImageFilter.GaussianBlur(2)))


def colorear(im: Image.Image, alfa: Image.Image, color: str, tono: str, arte: Arte) -> Image.Image:
    """D23 + D25: blanco y negro, o desaturado con el tono del lugar (o Halloween)."""
    if color == "byn":
        return ImageOps.grayscale(im).convert("RGB")
    t = arte.tonos[tono]
    if t.figura:
        return tenir_figura(im, alfa, t.colores, t.fuerza)
    return entonar(desaturar(im, arte.color.tope_desaturado), t.colores, t.fuerza)
