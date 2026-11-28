"""Lo que hace Python con las imágenes (Spec-790 D15: ComfyUI hace una sola cosa por llamada;
el resto, acá). Puro Pillow, sin GPU. Sale de los spikes E3c, E4 (ronda 2), C3, C5 y C5c, y de
los de la Spec-820 (S0–S2: la luz de Yael, la composición y la guía de la foto única).
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
def scribble(boceto: Image.Image) -> Image.Image:
    """T6.6: el boceto de Yael (líneas oscuras sobre un fondo cualquiera) → líneas blancas sobre
    negro, como espera el ControlNet. El fondo es la mediana (casi todo el lienzo)."""
    gris = ImageOps.grayscale(boceto)
    fondo = ImageStat.Stat(gris).median[0]
    return gris.point(
        lambda v: max(0, min(255, int((fondo - v) * 255 / max(fondo - 20, 1))))
    ).convert("RGB")


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


# ── Spec-820: la luz de Yael, antes y después de la foto única ──────────────────────
def iluminar_fondo(fondo: Image.Image, arte: Arte) -> Image.Image:
    """S0: lo que ya es claro y difuso (lo lejano, la niebla) se vuelve niebla blanca; lo demás
    (troncos y plantas cercanos) queda oscuro, en silueta. Abajo (lo cercano) entra menos niebla."""
    n = arte.luz.niebla
    lum_ = ImageOps.autocontrast(fondo.convert("L"), cutoff=1)
    w, h = lum_.size
    abajo = Image.linear_gradient("L").resize((w, h))
    vert = abajo.point(
        lambda v: round(255 * max(n.piso_abajo, min(1.0, 1.25 - (v / 255) ** 2 * 1.3)))
    )
    lejos = lum_.filter(ImageFilter.GaussianBlur(n.difuminado)).point(
        lambda v: round(255 * min(1.0, max(0.0, (v - n.desde) / n.rango)))
    )
    m = ImageChops.multiply(vert, lejos).point(lambda v: round(v * n.fuerza))
    oscuro = lum_.point(lambda v: round(v * n.oscuro))
    return Image.composite(Image.new("L", (w, h), n.gris), oscuro, m).convert("RGB")


def ojos(figura_rgb: Image.Image, alfa: Image.Image, arte: Arte) -> Image.Image:
    """Los ojos que brillan (lo cálido, saturado y muy claro dentro de la figura). Solo por
    brillo marcaba en amarillo lo que el flash aclara en la foto del personaje."""
    claro = ImageOps.grayscale(figura_rgb).point(lambda v: 255 if v > arte.luz.ojos_umbral else 0)
    calido = ImageChops.multiply(acentos(figura_rgb).point(lambda v: 255 if v > 64 else 0), claro)
    return ImageChops.multiply(calido, alfa.point(lambda v: 255 if v > 128 else 0))


def silueta(figura_rgb: Image.Image, arte: Arte) -> Image.Image:
    """La figura casi negra: el contraluz de Yael (D5)."""
    t, k = arte.luz.silueta_techo, arte.luz.silueta_factor
    return figura_rgb.convert("L").point(lambda v: min(t, round(v * k))).convert("RGB")


def con_halo(comp: Image.Image, alfa: Image.Image, ojos_m: Image.Image, arte: Arte) -> Image.Image:
    """D5: niebla clara justo detrás de la figura (la despega) y los ojos marcados."""
    hl, alto = arte.luz.halo, comp.height
    duro = alfa.point(lambda v: 255 if v > 128 else 0)
    halo = dilatar(duro, round(hl.radio * alto)).filter(
        ImageFilter.GaussianBlur(hl.difuminado * alto)
    )
    halo = ImageChops.subtract(halo, duro).point(lambda v: round(v * hl.fuerza))
    out = Image.composite(Image.new("RGB", comp.size, tuple(hl.color)), comp, halo)
    color_ojos = Image.new("RGB", comp.size, tuple(arte.luz.ojos_color))
    return Image.composite(
        color_ojos, out, dilatar(ojos_m, 2).filter(ImageFilter.GaussianBlur(1.5))
    )


def componer_con_luz(
    fondo: Image.Image, f: Image.Image, pos: tuple[int, int], alfa: Image.Image, arte: Arte
) -> Image.Image:
    """La composición de partida de la foto única: el fondo con niebla, la figura en silueta,
    el halo detrás y los ojos."""
    base = iluminar_fondo(fondo, arte)
    color = Image.new("RGB", base.size)
    color.paste(f.convert("RGB"), pos)
    comp = Image.composite(silueta(color, arte), base, alfa.filter(ImageFilter.GaussianBlur(1.5)))
    return con_halo(comp, alfa, ojos(color, alfa, arte), arte)


def mascara_tronco(alfa: Image.Image, arte: Arte) -> Image.Image | None:
    """S1c: un tronco vertical, de arriba a abajo del cuadro, que tapa parte del cuerpo (la cabeza
    y un brazo quedan a la vista). En proporción a la caja de la figura."""
    caja = alfa.point(lambda v: 255 if v > 128 else 0).getbbox()
    if caja is None:
        return None
    t, (w, h) = arte.luz.tronco, alfa.size
    x0, _, x1, _ = caja
    cx, ancho = x0 + t.centro * (x1 - x0), t.ancho * (x1 - x0) / 2
    abajo = ancho * t.abajo
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(
        [(cx - ancho, 0), (cx + ancho, 0), (cx + abajo * 1.02, h), (cx - abajo * 1.1, h)], fill=255
    )
    return m.filter(ImageFilter.GaussianBlur(2))


def pegar_tronco(comp: Image.Image, tronco: Image.Image, semilla: int, arte: Arte) -> Image.Image:
    """La corteza: vetas verticales gruesas y oscuras con grietas (la textura real la pone la
    foto). Con un ruido fino, Z-Image lo leía como un poste liso (tanda 15)."""
    lo, hi = arte.luz.tronco.oscuro
    w, h = comp.size
    vetas = Image.effect_noise((max(1, w // 14), max(1, h // 40)), 90 + semilla % 16)
    vetas = ImageOps.autocontrast(vetas.resize((w, h), Image.Resampling.BICUBIC))
    grietas = Image.effect_noise((max(1, w // 4), max(1, h // 6)), 120).resize(
        (w, h), Image.Resampling.NEAREST
    )
    corteza = ImageChops.darker(vetas, grietas.point(lambda v: 255 if v > 60 else 0))
    corteza = corteza.point(lambda v: round(lo + (hi - lo) * v / 255)).convert("RGB")
    return Image.composite(corteza, comp, tronco)


def profundidad(
    comp: Image.Image, alfa: Image.Image, arte: Arte, tronco: Image.Image | None = None
) -> Image.Image:
    """La guía de la foto única (S1): una profundidad falsa. Lo oscuro es cerca y lo claro (la
    niebla) lejos; la figura, cerca; el halo, lejos (el corte que la despega, D5); el tronco, lo
    más cercano. Los bordes como guía fallaban: la corteza corría la figura (tanda 10)."""
    luz, alto = arte.luz, comp.height
    duro = alfa.point(lambda v: 255 if v > 128 else 0)
    lejos = ImageOps.invert(ImageOps.grayscale(comp).filter(ImageFilter.GaussianBlur(6)))
    g = luz.profundidad_gamma
    lejos = ImageOps.autocontrast(lejos, cutoff=1).point(lambda v: round(255 * (v / 255) ** g))
    anillo_ = dilatar(duro, round(luz.profundidad_anillo * alto)).filter(
        ImageFilter.GaussianBlur(0.03 * alto)
    )
    lejos = Image.composite(Image.new("L", comp.size, 0), lejos, anillo_)
    cerca = Image.composite(
        Image.new("L", comp.size, 225 if tronco is not None else 255),
        lejos,
        alfa.filter(ImageFilter.GaussianBlur(2)),
    )
    if tronco is not None:
        cerca = Image.composite(Image.new("L", comp.size, 255), cerca, tronco)
    return cerca.convert("RGB")


def controlar_luz(foto: Image.Image, arte: Arte) -> Image.Image:
    """Después de la foto: negro y blanco de verdad, y la niebla clara un poco más arriba."""
    c = arte.luz.control
    im = ImageOps.autocontrast(lienzo(foto, arte), cutoff=(c.negro, c.blanco), preserve_tone=True)
    m = (
        im.convert("L")
        .filter(ImageFilter.GaussianBlur(30))
        .point(
            lambda v: round(
                255 * min(1.0, max(0.0, (v - c.niebla_desde) / c.niebla_rango)) * c.niebla_fuerza
            )
        )
    )
    claro = ImageChops.screen(im, Image.new("RGB", im.size, tuple(c.niebla_color)))
    return Image.composite(claro, im, m)


def despegar(foto: Image.Image, figura: Image.Image, arte: Arte) -> Image.Image:
    """D5: un anillo de niebla apenas más clara alrededor de la figura (no sobre ella)."""
    d, alto = arte.luz.despegar, foto.height
    m = figura.convert("L").resize(foto.size).point(lambda v: 255 if v > 128 else 0)
    anillo_ = ImageChops.subtract(
        dilatar(m, round(d.anillo * alto)).filter(ImageFilter.GaussianBlur(d.difuminado * alto)), m
    )
    claro = ImageChops.screen(foto, Image.new("RGB", foto.size, tuple(d.color)))
    return Image.composite(claro, foto, anillo_.point(lambda v: round(v * d.fuerza)))


def mate(foto: Image.Image, figura: Image.Image, arte: Arte) -> Image.Image:
    """D7: dentro de la figura las luces se aplastan (sin brillo húmedo ni de plástico). Los ojos
    (lo cálido y muy claro) y el borde (la luz de contorno) quedan."""
    mt, alto = arte.luz.mate, foto.height
    m = figura.convert("L").resize(foto.size).point(lambda v: 255 if v > 128 else 0)
    nucleo = erosionar(m, max(1, round(mt.nucleo * alto))).filter(ImageFilter.GaussianBlur(3))
    nucleo = ImageChops.subtract(
        nucleo, dilatar(acentos(foto), 3).filter(ImageFilter.GaussianBlur(2))
    )
    t, k = mt.techo, mt.compresion
    aplastada = foto.point(lambda v: v if v < t else round(t + (v - t) * k))
    return Image.composite(aplastada, foto, nucleo)


def devolver_ojos(
    final: Image.Image, comp: Image.Image, figura: Image.Image, arte: Arte
) -> Image.Image:
    """Si la foto apagó los ojos (ninguna luz cálida dentro de la figura, tanda 15), vuelve el
    brillo de la composición, solo donde la cabeza sigue estando (dentro de la figura de la foto)."""
    m = figura.convert("L").resize(final.size).point(lambda v: 255 if v > 128 else 0)
    if ImageChops.multiply(acentos(final), m).point(lambda v: 255 if v > 64 else 0).getbbox():
        return final
    ojos_comp = acentos(comp.resize(final.size)).point(lambda v: 255 if v > 64 else 0)
    ojos_comp = ImageChops.multiply(ojos_comp, m)
    if ojos_comp.getbbox() is None:
        return final
    brillo = Image.new("RGB", final.size, tuple(arte.luz.ojos_color))
    halo = dilatar(ojos_comp, 3).filter(ImageFilter.GaussianBlur(3))
    return Image.composite(ImageChops.screen(final, brillo), final, halo)


def contar_ojos(im: Image.Image, lado: int = 320, minimo: int = 2) -> int:
    """Cuántas luces cálidas sueltas hay (los ojos que brillan). 4 o más = una cabeza de más
    (tanda 18). Sobre una versión chica y por manchas conectadas, sin numpy."""
    chica = im.convert("RGB").copy()
    chica.thumbnail((lado, lado))
    m = acentos(chica).point(lambda v: 255 if v > 64 else 0)
    w, h = m.size
    px = m.load()
    vistos: set[tuple[int, int]] = set()
    manchas = 0
    for y in range(h):
        for x in range(w):
            if px[x, y] == 0 or (x, y) in vistos:
                continue
            pila, tam = [(x, y)], 0
            vistos.add((x, y))
            while pila:
                cx, cy = pila.pop()
                tam += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and (nx, ny) not in vistos:
                        vistos.add((nx, ny))
                        pila.append((nx, ny))
            if tam >= minimo:
                manchas += 1
    return manchas


def medir_luz(im: Image.Image) -> dict[str, int]:
    """La luz de una imagen (Spec-820 §1.1): media, p5 y p95 de la luminancia."""
    g = im.convert("L")
    hist, n = g.histogram(), g.width * g.height

    def pc(q: float) -> int:
        acum = 0
        for i, v in enumerate(hist):
            acum += v
            if acum >= n * q:
                return i
        return 255

    return {"media": round(ImageStat.Stat(g).mean[0]), "p5": pc(0.05), "p95": pc(0.95)}
