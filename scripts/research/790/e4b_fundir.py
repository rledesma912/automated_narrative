"""Spike E4/E5 ronda 2 (Spec-790 §10.0): fundir sin halo.

La ronda 1 (`e4_fundir.py`) mostró que Qwen aclara toda la zona y deja un halo con la forma de
la máscara. Esta ronda prueba la propuesta del informe, siempre «Qwen hace una cosa, Python el
resto»:

  py       solo Python: la figura se oscurece hasta la luz del lugar (media y techo según el
           anillo de fondo que la rodea), grano como el del fondo, borde apenas difuminado y,
           si pisa el piso, una sombra de contacto dibujada (elipse oscura difuminada)
  py_qwen  lo de `py` → zona con margen → Qwen con una instrucción acotada (no tocar el fondo
           ni su brillo, no agregar niebla ni luz) → Python iguala la exposición de la salida
           con la del original en el anillo FUERA de la máscara (media y desvío por canal) →
           pega dentro de la máscara d1 / d2 con un borde difuminado más ancho

Mide lo mismo que la ronda 1 (fuera de máscara = 0, cambio de bordes de la figura) y además el
«halo»: diferencia de brillo medio entre la franja de máscara que no es figura y el original.

    uv run python e4b_fundir.py [--semillas 11,22,33] [--solo-grilla]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy, ComfyError, grilla  # noqa: E402
from e1_personaje import grafo_qwen  # noqa: E402
from e4_fundir import (  # noqa: E402
    ALTO,
    CENTRO_X,
    ESCENAS,
    PIE_Y,
    cambio_de_figura,
    dilatar,
    erosionar,
    fuera_de_mascara,
)

SALIDAS = AQUI / "e4b" / "salidas"
DILATACIONES = {"d1": 0.01, "d2": 0.02}
BORDE = 16  # px del difuminado del pegado, hacia adentro (la ronda 1 usaba 8)
ANILLO = 0.04  # ancho del anillo de fondo para medir la luz, en altos del cuadro
MARGEN = 0.12
# La figura queda a FIGURA_X veces el brillo medio del lugar que la rodea (tiene que leerse a
# 120 px, por eso no 1×) y sus luces no pasan del TECHO.
FIGURA_X, TECHO, PISO = 1.7, 0.80, 30.0  # PISO: brillo medio mínimo de la figura (0–255)
GRANO = 4  # sigma del ruido gris sumado a la figura
SOMBRA_OPACIDAD = 0.75

PROMPT_FUNDIR = (
    "Make the figure look photographed in this place. Only adjust the figure itself: its "
    "edges, its shading and how the faint light of the scene falls on it, and keep the dark "
    "contact shadow under it dark. Do not change the background, do not make anything "
    "brighter, do not add fog, glow or light. Keep the figure's shape, pose, face and details "
    "exactly the same."
)


# ── Python ────────────────────────────────────────────────────────────────────────
def lum(img: Image.Image, m: Image.Image | None = None) -> tuple[float, float]:
    st = ImageStat.Stat(img.convert("L"), m)
    return st.mean[0], st.stddev[0]


def anillo(m: Image.Image, ancho: int) -> Image.Image:
    return ImageChops.subtract(dilatar(m, ancho), m)


def preparar(e: dict) -> tuple[Image.Image, Image.Image, tuple, dict]:
    """Compone con la figura ya oscurecida, con grano y sombra. Devuelve (compuesto, alfa,
    caja, datos)."""
    fondo = Image.open(e["escena"]).convert("RGB")
    ancho_c, alto_c = fondo.size
    original = Image.open(e["figura"]).convert("RGBA")
    a = original.getchannel("A")
    fig = original.crop(a.point(lambda v: 255 if v > 8 else 0).getbbox())
    escala = ALTO * alto_c / fig.height
    fig = fig.resize(
        (round(fig.width * escala), round(fig.height * escala)), Image.Resampling.LANCZOS
    )
    x = round(CENTRO_X * ancho_c - fig.width / 2)
    y = alto_c - fig.height if e["apoyo"] == "borde" else round(PIE_Y * alto_c - fig.height)
    alfa = Image.new("L", fondo.size, 0)
    alfa.paste(fig.getchannel("A"), (x, y))
    duro = alfa.point(lambda v: 255 if v > 128 else 0)

    # La luz del lugar: el anillo de fondo alrededor de la figura.
    media_lugar, _ = lum(fondo, anillo(duro, round(ANILLO * alto_c)))
    rgb = fig.convert("RGB")
    media_fig, _ = lum(rgb, fig.getchannel("A").point(lambda v: 255 if v > 128 else 0))
    objetivo = min(max(FIGURA_X * media_lugar, PISO), media_fig)
    duro_fig = fig.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    # Curva gamma con techo (como E3c): se busca la gamma que deja la media en el objetivo;
    # conserva el detalle de las sombras mejor que escalar.
    lo, hi = 0.3, 6.0
    for _ in range(25):
        k = (lo + hi) / 2
        tabla = [round(255 * TECHO * (v / 255) ** k) for v in range(256)]
        if lum(rgb.point(tabla * 3), duro_fig)[0] > objetivo:
            lo = k
        else:
            hi = k
    rgb = rgb.point(tabla * 3)
    ruido = Image.effect_noise(rgb.size, GRANO).convert("RGB")
    rgb = ImageChops.add(rgb, ruido, 1.0, -128)
    fig_alfa = fig.getchannel("A").filter(ImageFilter.GaussianBlur(1.2))

    compuesto = fondo.copy()
    if e["apoyo"] == "piso":
        sombra = Image.new("L", fondo.size, 0)
        d = ImageDraw.Draw(sombra)
        x1, y1 = x + fig.width, y + fig.height
        cx, ancho = (x + x1) / 2, fig.width
        d.ellipse(
            (cx - 0.55 * ancho, y1 - 0.035 * alto_c, cx + 0.6 * ancho, y1 + 0.02 * alto_c),
            fill=round(255 * SOMBRA_OPACIDAD),
        )
        sombra = sombra.filter(ImageFilter.GaussianBlur(0.012 * alto_c))
        negro = Image.new("RGB", fondo.size, (0, 0, 0))
        compuesto = Image.composite(negro, compuesto, sombra)
    compuesto.paste(rgb, (x, y), fig_alfa)
    datos = {"luz_lugar": round(media_lugar, 1), "luz_figura": round(media_fig, 1), "k": round(k, 3)}
    return compuesto, alfa, (x, y, x + fig.width, y + fig.height), datos


def mascara(alfa: Image.Image, caja, dilatacion: float, apoyo: str) -> Image.Image:
    ancho_c, alto_c = alfa.size
    m = dilatar(alfa.point(lambda v: 255 if v > 32 else 0), round(dilatacion * alto_c))
    if apoyo == "piso":
        x0, _, x1, y1 = caja
        cx, ancho = (x0 + x1) / 2, x1 - x0
        ImageDraw.Draw(m).ellipse(
            (cx - 0.65 * ancho, y1 - 0.05 * alto_c, cx + 0.7 * ancho, y1 + 0.035 * alto_c), fill=255
        )
    return m


def zona(m: Image.Image) -> tuple[int, int, int, int]:
    ancho_c, alto_c = m.size
    x0, y0, x1, y1 = m.getbbox()
    mg = round(MARGEN * alto_c)
    return max(0, x0 - mg), max(0, y0 - mg), min(ancho_c, x1 + mg), min(alto_c, y1 + mg)


def igualar(editado: Image.Image, original: Image.Image, ref: Image.Image) -> Image.Image:
    """Lleva media y desvío de cada canal de `editado` a los de `original`, medidos en `ref`
    (el anillo fuera de la máscara, donde lo editado no tendría que haber cambiado)."""
    se, so = ImageStat.Stat(editado, ref), ImageStat.Stat(original, ref)
    tablas = []
    for c in range(3):
        ke = so.stddev[c] / max(se.stddev[c], 1)
        tablas += [max(0, min(255, round((v - se.mean[c]) * ke + so.mean[c]))) for v in range(256)]
    return editado.point(tablas)


def pegar(compuesto, editado_zona, caja_zona, m) -> Image.Image:
    x0, y0, x1, y1 = caja_zona
    editado = compuesto.copy()
    editado.paste(editado_zona, (x0, y0))
    suave = erosionar(m, BORDE).filter(ImageFilter.GaussianBlur(BORDE / 2))
    suave = ImageChops.multiply(suave, m)
    return Image.composite(editado, compuesto, suave)


def halo(fundido, compuesto, m, alfa) -> float:
    """Brillo medio agregado en la franja de máscara que no es figura (la ronda 1: halo)."""
    franja = ImageChops.subtract(m, alfa.point(lambda v: 255 if v > 32 else 0))
    return round(lum(fundido, franja)[0] - lum(compuesto, franja)[0], 2)


# ── la corrida ───────────────────────────────────────────────────────────────────
async def main(semillas: list[int]) -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas: dict = {}
    async with Comfy() as c:
        await c.liberar()
        for k, e in ESCENAS.items():
            compuesto, alfa, caja, datos = preparar(e)
            compuesto.save(SALIDAS / f"{k}_py.png")
            alto_c = compuesto.height
            mascaras = {dn: mascara(alfa, caja, dv, e["apoyo"]) for dn, dv in DILATACIONES.items()}
            for dn, m in mascaras.items():
                m.save(SALIDAS / f"{k}_mascara_{dn}.png")
            caja_zona = zona(mascaras["d2"])
            compuesto.crop(caja_zona).save(SALIDAS / f"{k}_zona.png")
            sub = await c.subir(SALIDAS / f"{k}_zona.png")
            medidas[k] = {"preparar": datos, "caja_zona": caja_zona}
            for s in semillas:
                clave = f"{k}_s{s}"
                try:
                    r = await c.correr(grafo_qwen(sub, PROMPT_FUNDIR, s, f"spec790/e4b/{clave}"))
                except ComfyError as err:
                    medidas[clave] = {"error": str(err)}
                    print(clave, "ERROR", err, flush=True)
                    continue
                crudo = SALIDAS / f"{clave}_qwen.png"
                await c.bajar(r.imagenes[0], crudo)
                x0, y0, x1, y1 = caja_zona
                salida = Image.open(crudo).convert("RGB").resize(
                    (x1 - x0, y1 - y0), Image.Resampling.LANCZOS
                )
                orig_zona = compuesto.crop(caja_zona)
                medidas[clave] = {"segundos": r.segundos, "vram_pico_mb": r.vram_pico_mb}
                for dn, m in mascaras.items():
                    m_zona = m.crop(caja_zona)
                    ref = anillo(m_zona, round(ANILLO * alto_c))
                    for modo, ed in (("crudo", salida), ("igualado", igualar(salida, orig_zona, ref))):
                        f = pegar(compuesto, ed, caja_zona, m)
                        f.save(SALIDAS / f"{k}_{dn}_{modo}_s{s}.png")
                        medidas[clave][f"{dn}_{modo}"] = {
                            "fuera_de_mascara": fuera_de_mascara(f, compuesto, m),
                            "cambio_figura": cambio_de_figura(compuesto, f, alfa),
                            "halo": halo(f, compuesto, m, alfa),
                        }
                print(clave, json.dumps(medidas[clave]), flush=True)
                (SALIDAS / "medidas.json").write_text(json.dumps(medidas, indent=2))
        await c.liberar()
    return medidas


def grillas(semillas: list[int]) -> None:
    r1 = AQUI / "e4" / "salidas"
    for k in ESCENAS:
        filas = [
            (
                "base",
                [
                    ("ronda 1 tosco", r1 / f"{k}_tosco.png"),
                    ("ronda 1 d2 abajo s22", r1 / f"{k}_d2_abajo_s22.png"),
                    ("py (solo Python)", SALIDAS / f"{k}_py.png"),
                ],
            )
        ]
        for s in semillas:
            celdas = [
                (f"{dn} {modo}", SALIDAS / f"{k}_{dn}_{modo}_s{s}.png")
                for dn in DILATACIONES
                for modo in ("crudo", "igualado")
            ]
            filas.append((f"s{s}", [c for c in celdas if c[1].exists()]))
        print(grilla(filas, SALIDAS / f"grilla_{k}.png", ancho_celda=300))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--semillas", default="11,22,33")
    ap.add_argument("--solo-grilla", action="store_true")
    a = ap.parse_args()
    sem = [int(x) for x in a.semillas.split(",")]
    if not a.solo_grilla:
        asyncio.run(main(sem))
    grillas(sem)
