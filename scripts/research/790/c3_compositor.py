"""Spike C3 (Spec-790 §2.11, D21): el compositor. Las 4 opciones = las 4 plantillas de Yael.

Por caso (la torre, la coneja), con las piezas ya armadas (escenario de E3c, personaje de E2):
  1. Lo importante del escenario: BiRefNet sobre el escenario (la torre, la mansión).
  2. Por plantilla (A_der, A_izq, C_primer_plano, B_lugar), Python:
     - ubica la figura (lado, alto, recorte de primer plano) y, si la figura taparía lo importante
       del escenario, prueba el escenario espejado y se queda con el que menos se tapa;
     - oscurece la figura según el lugar + grano + sombra (E4 ronda 2);
     - funde con Qwen en la zona, iguala la exposición y pega con la máscara d1 (E4 ronda 2);
     - arma el título con las reglas de C2 y lo pone en la ESQUINA que menos tapa: la cara de la
       figura (peso 4), la figura (1), lo importante del escenario (1,5) y la esquina de la duración
       (prohibida); con la bajada abajo, chica.
  3. Hoja: las 4 en grande y a 120 px, al lado de la miniatura real de Yael de esa historia.

    uv run python c3_compositor.py [--semilla 22] [--sin-qwen]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2_titulo import FUENTE, dibujar, reglas  # noqa: E402
from comun import AQUI, Comfy  # noqa: E402
from e1_personaje import grafo_qwen  # noqa: E402
from e2_recortar import grafo_birefnet  # noqa: E402
from e4_fundir import dilatar, erosionar  # noqa: E402
from e4b_fundir import ANILLO, PROMPT_FUNDIR, anillo, igualar, lum  # noqa: E402

SALIDAS = AQUI / "c3" / "salidas"
CANAL = AQUI / "insumos" / "canal_yt"
W, H = 1280, 720

CASOS = {
    "torre": {
        "escena": AQUI / "e3c" / "salidas" / "torre_previo_45_s33.png",
        "figura": AQUI / "e2" / "salidas" / "torre_piel_qwen_b_s22_a.png",
        "apoyo": "piso",  # cuerpo entero, pisa el piso
        "gancho": "SIGUE ESTAS REGLAS PARA SOBREVIVIR",
        "bajada": "NO VER ANTES DE DORMIR",
        "real": "uW07ikm2pkQ",
    },
    "coneja": {
        "escena": AQUI / "e3c" / "salidas" / "mansion_previo_45_s22.png",
        "figura": AQUI / "e2" / "salidas" / "mansion_qwen_b_s22_a.png",
        "apoyo": "borde",  # de la cintura para arriba: va pegada al borde de abajo
        "gancho": "3 HISTORIAS DE HALLOWEEN",
        "bajada": "(para NO dormir)",
        "real": "dW0nYhKpfqg",
    },
}

# D21 / C1 (catalogo): lado = centro x de la figura; alto = fracción del cuadro; recorte = qué parte
# de arriba de la figura se usa (1 = toda; 0,45 = cabeza y torso, primer plano).
PLANTILLAS = {
    "A_der": {"cx": 0.70, "alto": 0.92, "recorte": 1.0, "lado_titulo": "izquierda"},
    "A_izq": {"cx": 0.30, "alto": 0.92, "recorte": 1.0, "lado_titulo": "derecha"},
    "C_primer_plano": {"cx": 0.68, "alto": 1.0, "recorte": 0.70, "lado_titulo": "izquierda"},
    "B_lugar": {"cx": 0.46, "alto": 0.50, "recorte": 1.0, "lado_titulo": None},
}
MARGEN = 0.035
TITULO_ANCHO, TITULO_ALTO = 0.48, 0.66  # el bloque de Yael: ~45 % del ancho
ESQUINA_LIBRE = (1.0 - 0.20, 1.0 - 0.15)  # la duración de YouTube, abajo a la derecha
FIGURA_X, TECHO, PISO, GRANO = 1.7, 0.80, 30.0, 4
BORDE = 16


# ── piezas ───────────────────────────────────────────────────────────────────────
def escenario(path: Path, espejo: bool) -> Image.Image:
    im = ImageOps.fit(Image.open(path).convert("RGB"), (W, H), Image.Resampling.LANCZOS)
    return ImageOps.mirror(im) if espejo else im


def figura_recortada(path: Path, recorte: float) -> Image.Image:
    f = Image.open(path).convert("RGBA")
    f = f.crop(f.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
    if recorte < 1:
        f = f.crop((0, 0, f.width, round(f.height * recorte)))
    return f


def ubicar(fig: Image.Image, p: dict, apoyo: str) -> tuple[Image.Image, tuple[int, int]]:
    escala = p["alto"] * H / fig.height
    f = fig.resize((round(fig.width * escala), round(fig.height * escala)), Image.Resampling.LANCZOS)
    x = round(p["cx"] * W - f.width / 2)
    if p["recorte"] < 1 or apoyo == "borde":
        y = H - f.height + (round(0.04 * H) if p["recorte"] < 1 else 0)  # cortada por el borde de abajo
    elif p["alto"] < 0.7:
        y = round(0.86 * H - f.height)  # chica: en el plano medio, los pies en el piso del fondo
    else:
        y = round(0.98 * H - f.height)
    return f, (x, y)


def alfa_en_cuadro(f: Image.Image, pos) -> Image.Image:
    a = Image.new("L", (W, H), 0)
    a.paste(f.getchannel("A"), pos)
    return a


def cara(alfa: Image.Image) -> Image.Image:
    """La cara: el 22 % de arriba de la figura (donde están los ojos y la máscara)."""
    x0, y0, x1, y1 = alfa.getbbox()
    m = Image.new("L", (W, H), 0)
    corte = alfa.crop((0, y0, W, y0 + round(0.22 * (y1 - y0))))
    m.paste(corte, (0, y0))
    return dilatar(m.point(lambda v: 255 if v > 32 else 0), 12)


def cuanto(m: Image.Image, area: Image.Image) -> float:
    """Fracción de `area` (0–255) que cae dentro de `m`."""
    inter = ImageChops.multiply(m, area).histogram()
    tot = area.histogram()
    s_tot = sum(i * c for i, c in enumerate(tot))
    return sum(i * c for i, c in enumerate(inter)) / 255 / s_tot if s_tot else 0


def oscurecer(f: Image.Image, fondo: Image.Image, alfa: Image.Image) -> Image.Image:
    duro = alfa.point(lambda v: 255 if v > 128 else 0)
    media_lugar, _ = lum(fondo, anillo(duro, round(ANILLO * H)))
    rgb = f.convert("RGB")
    duro_fig = f.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    media_fig, _ = lum(rgb, duro_fig)
    objetivo = min(max(FIGURA_X * media_lugar, PISO), media_fig)
    lo, hi = 0.3, 6.0
    for _ in range(25):
        k = (lo + hi) / 2
        tabla = [round(255 * TECHO * (v / 255) ** k) for v in range(256)]
        if lum(rgb.point(tabla * 3), duro_fig)[0] > objetivo:
            lo = k
        else:
            hi = k
    rgb = rgb.point(tabla * 3)
    rgb = ImageChops.add(rgb, Image.effect_noise(rgb.size, GRANO).convert("RGB"), 1.0, -128)
    out = rgb.convert("RGBA")
    out.putalpha(f.getchannel("A").filter(ImageFilter.GaussianBlur(1.2)))
    return out


def componer(fondo: Image.Image, f: Image.Image, pos, apoyo: str, recorte: float) -> Image.Image:
    comp = fondo.copy()
    if apoyo == "piso" and recorte == 1:
        x, y = pos
        sombra = Image.new("L", (W, H), 0)
        cx, y1 = x + f.width / 2, y + f.height
        ImageDraw.Draw(sombra).ellipse(
            (cx - 0.5 * f.width, y1 - 0.03 * H, cx + 0.55 * f.width, y1 + 0.02 * H), fill=190
        )
        comp = Image.composite(Image.new("RGB", (W, H)), comp, sombra.filter(ImageFilter.GaussianBlur(0.012 * H)))
    comp.paste(f, pos, f)
    return comp


def mascara_fundir(alfa: Image.Image) -> Image.Image:
    return dilatar(alfa.point(lambda v: 255 if v > 32 else 0), round(0.01 * H))


def zona(m: Image.Image) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = m.getbbox()
    mg = round(0.12 * H)
    return max(0, x0 - mg), max(0, y0 - mg), min(W, x1 + mg), min(H, y1 + mg)


def pegar(comp, editado_zona, caja, m) -> Image.Image:
    x0, y0, _, _ = caja
    ed = comp.copy()
    ed.paste(editado_zona, (x0, y0))
    suave = ImageChops.multiply(erosionar(m, BORDE).filter(ImageFilter.GaussianBlur(BORDE / 2)), m)
    return Image.composite(ed, comp, suave)


# ── título ───────────────────────────────────────────────────────────────────────
def bloque_titulo(gancho: str, bajada: str | None, alinear: str) -> Image.Image:
    bw, bh = round(TITULO_ANCHO * W), round(TITULO_ALTO * H)
    b = dibujar(reglas(gancho), ancho_c=bw, alto_c=bh - (60 if bajada else 0), alinear=alinear)
    b = b.crop(b.getbbox())
    if bajada:
        f = ImageFont.truetype(str(FUENTE), 30)
        d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
        tw = d0.textlength(bajada, font=f)
        nuevo = Image.new("RGBA", (max(b.width, round(tw) + 10), b.height + 50), (0, 0, 0, 0))
        nuevo.alpha_composite(b, (0, 0))
        capa = Image.new("RGBA", nuevo.size, (0, 0, 0, 0))
        ImageDraw.Draw(capa).text((0 if alinear == "izquierda" else nuevo.width - tw, b.height + 6), bajada,
                                  font=f, fill=(235, 235, 235))
        sombra = Image.new("RGBA", nuevo.size, (0, 0, 0, 0))
        sombra.putalpha(capa.getchannel("A").filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(4)))
        nuevo = Image.alpha_composite(Image.alpha_composite(nuevo, sombra), capa)
        b = nuevo
    return b


def esquinas(b: Image.Image, lado: str | None) -> dict[str, tuple[int, int]]:
    mx, my = round(MARGEN * W), round(MARGEN * H)
    todas = {
        "arriba_izquierda": (mx, my),
        "abajo_izquierda": (mx, H - my - b.height),
        "arriba_derecha": (W - mx - b.width, my),
        "abajo_derecha": (W - mx - b.width, H - my - b.height),
    }
    if lado:
        todas = {k: v for k, v in todas.items() if lado in k}
    return todas


def ubicar_titulo(b: Image.Image, protegido: dict[str, Image.Image], lado: str | None):
    libre = Image.new("L", (W, H), 0)
    ImageDraw.Draw(libre).rectangle((round(ESQUINA_LIBRE[0] * W), round(ESQUINA_LIBRE[1] * H), W, H), fill=255)
    pesos = {"cara": 4.0, "figura": 1.0, "escena": 1.5}
    mejor = None
    for nombre, (x, y) in esquinas(b, lado).items():
        a = Image.new("L", (W, H), 0)
        a.paste(dilatar(b.getchannel("A").point(lambda v: 255 if v > 40 else 0), 6), (x, y))
        if ImageChops.multiply(libre, a).histogram()[255] > 0:  # nada del título bajo la duración
            continue
        costo = sum(pesos[k] * cuanto(a, m) for k, m in protegido.items())
        if mejor is None or costo < mejor[0]:
            mejor = (costo, nombre, (x, y))
    return mejor


# ── la corrida ───────────────────────────────────────────────────────────────────
async def importantes(c: Comfy) -> dict[str, Image.Image]:
    out = {}
    for k, caso in CASOS.items():
        destino = SALIDAS / f"{k}_importante.png"
        if not destino.exists():
            fondo = SALIDAS / f"{k}_escena.png"
            escenario(caso["escena"], False).save(fondo)
            r = await c.correr(grafo_birefnet(await c.subir(fondo), f"spec790/c3/{k}_imp"))
            await c.bajar(r.imagenes[0], destino)
        out[k] = Image.open(destino).convert("L").resize((W, H))
    return out


async def main(semilla: int, con_qwen: bool) -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas: dict = {}
    async with Comfy() as c:
        await c.liberar()
        imp = await importantes(c)
        for k, caso in CASOS.items():
            for pn, p in PLANTILLAS.items():
                fig = figura_recortada(caso["figura"], p["recorte"])
                f, pos = ubicar(fig, p, caso["apoyo"])
                alfa = alfa_en_cuadro(f, pos)
                # ¿la figura tapa lo importante del escenario? probar el espejo
                opciones = []
                for espejo in (False, True):
                    m_imp = ImageOps.mirror(imp[k]) if espejo else imp[k]
                    opciones.append((cuanto(alfa, m_imp.point(lambda v: 255 if v > 128 else 0)), espejo))
                tapado, espejo = min(opciones)
                fondo = escenario(caso["escena"], espejo)
                m_imp = (ImageOps.mirror(imp[k]) if espejo else imp[k]).point(lambda v: 255 if v > 128 else 0)
                f2 = oscurecer(f, fondo, alfa)
                comp = componer(fondo, f2, pos, caso["apoyo"], p["recorte"])
                clave = f"{k}_{pn}"
                comp.save(SALIDAS / f"{clave}_comp.png")
                final = comp
                if con_qwen:
                    m = mascara_fundir(alfa)
                    caja = zona(m)
                    comp.crop(caja).save(SALIDAS / f"{clave}_zona.png")
                    r = await c.correr(grafo_qwen(await c.subir(SALIDAS / f"{clave}_zona.png"), PROMPT_FUNDIR,
                                                  semilla, f"spec790/c3/{clave}"))
                    crudo = SALIDAS / f"{clave}_qwen.png"
                    await c.bajar(r.imagenes[0], crudo)
                    x0, y0, x1, y1 = caja
                    sal = Image.open(crudo).convert("RGB").resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
                    m_z = m.crop(caja)
                    sal = igualar(sal, comp.crop(caja), anillo(m_z, round(ANILLO * H)))
                    final = pegar(comp, sal, caja, m)
                    medidas.setdefault(clave, {})["qwen_s"] = r.segundos
                # el título en la esquina que menos tapa
                protegido = {"cara": cara(alfa), "figura": alfa.point(lambda v: 255 if v > 32 else 0), "escena": m_imp}
                lado = p["lado_titulo"]
                mejor = None
                for alinear in ("izquierda", "derecha"):
                    if lado and alinear != lado:
                        continue
                    b = bloque_titulo(caso["gancho"], caso["bajada"], alinear)
                    r_t = ubicar_titulo(b, protegido, alinear)
                    if r_t and (mejor is None or r_t[0] < mejor[0][0]):
                        mejor = (r_t, b)
                (costo, esquina, (tx, ty)), b = mejor
                out = final.convert("RGBA")
                out.alpha_composite(b, (tx, ty))
                out = out.convert("RGB")
                out.save(SALIDAS / f"{clave}.png")
                medidas.setdefault(clave, {}).update({
                    "espejo": espejo, "figura_tapa_escena": round(tapado, 3),
                    "titulo_esquina": esquina, "titulo_costo": round(costo, 3),
                })
                print(clave, medidas[clave], flush=True)
        await c.liberar()
    (SALIDAS / "medidas.json").write_text(json.dumps(medidas, indent=2))
    return medidas


def hojas() -> None:
    for k, caso in CASOS.items():
        cw, ch = 640, 360
        o = Image.new("RGB", (cw * 3 + 40, ch * 2 + 160), (18, 18, 18))
        d = ImageDraw.Draw(o)
        real = Image.open(CANAL / f"{caso['real']}.jpg").convert("RGB").resize((cw, ch))
        o.paste(real, (0, 30))
        d.text((8, 8), "Yael (real)", fill=(255, 255, 0))
        for i, pn in enumerate(PLANTILLAS):
            im = Image.open(SALIDAS / f"{k}_{pn}.png").convert("RGB")
            x, y = cw * (1 + i % 2) + 20 * (1 + i % 2), 30 + (i // 2) * (ch + 30)
            o.paste(im.resize((cw, ch)), (x, y))
            d.text((x + 8, y - 22), pn, fill=(255, 255, 0))
        # a 120 px: la real y las 4
        y = ch * 2 + 100
        for i, (nombre, im) in enumerate([("real", real)] + [(pn, Image.open(SALIDAS / f"{k}_{pn}.png")) for pn in PLANTILLAS]):
            o.paste(im.convert("RGB").resize((120, 68)), (10 + i * 140, y))
        d.text((10, y - 20), "a 120 px: real, A_der, A_izq, C_primer_plano, B_lugar", fill=(255, 255, 0))
        o.save(SALIDAS / f"hoja_{k}.jpg", quality=90)
        print(SALIDAS / f"hoja_{k}.jpg")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--semilla", type=int, default=22)
    ap.add_argument("--sin-qwen", action="store_true")
    ap.add_argument("--solo-hoja", action="store_true")
    a = ap.parse_args()
    if not a.solo_hoja:
        asyncio.run(main(a.semilla, not a.sin_qwen))
    hojas()
