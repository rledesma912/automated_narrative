"""Spikes E4 + E5 (Spec-790 §10.0, §2.5): fundir el personaje en el escenario con una máscara
automática, sin tocar el fondo.

E4 (fundir), por escena y semilla:
  zona    Python compone (escenario de E3c + recorte de E2, plano medio a la izquierda), recorta
          la ZONA del personaje con margen, Qwen-Edit 2511 + Lightning la funde (luz, niebla,
          sombra de contacto, sin cambiar la figura) y Python la pega de vuelta SOLO dentro de
          la máscara, con el borde difuminado hacia adentro
  global  control: Qwen-Edit sobre la composición entera, sin máscara (el problema del video
          de ILM: corre el fondo, le cambia el tono)

E5 (la máscara, solo Python, sobre la misma salida de `zona`): dilatación del alfa 1 %, 2 %
y 4 % del alto × franja de sombra «abajo» y «abajo_derecha» (del lado contrario a la luna).

Mide: la diferencia de píxeles fuera de la máscara (tiene que ser 0) y cuánto cambió la figura
adentro (bordes del compuesto vs. del fundido), para proponer el umbral de la revisión.

    uv run python e4_fundir.py [--semillas 11,22,33] [--solo-grilla]
Solo Pillow (sin numpy/scipy: no están en el proyecto).
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

SALIDAS = AQUI / "e4" / "salidas"
E2 = AQUI / "e2" / "salidas"
E3C = AQUI / "e3c" / "salidas"

ESCENAS = {
    "torre": {
        "escena": E3C / "torre_previo_45_s33.png",
        "figura": E2 / "torre_piel_qwen_b_s22_a.png",
        "apoyo": "piso",
    },
    "mansion": {
        "escena": E3C / "mansion_previo_45_s22.png",
        "figura": E2 / "mansion_qwen_b_s22_a.png",
        "apoyo": "borde",
    },
}
# arte.yaml (§2.2): plano_medio = 75 % del alto; lado izquierda = centro en x 0,28.
ALTO, CENTRO_X, PIE_Y = 0.75, 0.28, 0.96
DILATACIONES = {"d1": 0.01, "d2": 0.02, "d4": 0.04}
FRANJAS = {"abajo": 0.0, "abajo_derecha": 0.35}  # corrimiento de la sombra, en anchos de figura
FRANJA_ALTO = 0.10  # alto de la franja de sombra, en altos del cuadro
BORDE = 8  # px del difuminado del pegado (hacia adentro de la máscara)
MARGEN = 0.12  # margen de la zona alrededor de la máscara más grande, en altos del cuadro

PROMPT_FUNDIR = (
    "Blend the figure naturally into this night photograph, as if it was photographed there: "
    "match the darkness, the faint diffuse moonlight, the thick fog and the black and white "
    "film grain of the place. The figure is partly in shadow and partly swallowed by the "
    "fog. Add a soft, dark contact shadow on the ground under it. Keep the figure's shape, "
    "pose, face and details exactly the same. Do not add anything else and do not change "
    "the background."
)


# ── composición y máscara (Python puro) ────────────────────────────────────────
def componer(
    escena: Path, figura: Path, apoyo: str = "piso"
) -> tuple[Image.Image, Image.Image, tuple[int, int, int, int]]:
    """Devuelve (compuesto RGB, alfa de la figura en el cuadro, caja de la figura)."""
    fondo = Image.open(escena).convert("RGB")
    ancho_c, alto_c = fondo.size
    original = Image.open(figura).convert("RGBA")
    a = original.getchannel("A")
    fig = original.crop(a.point(lambda v: 255 if v > 8 else 0).getbbox())
    escala = ALTO * alto_c / fig.height
    fig = fig.resize(
        (round(fig.width * escala), round(fig.height * escala)), Image.Resampling.LANCZOS
    )
    x = round(CENTRO_X * ancho_c - fig.width / 2)
    # «borde»: la figura llega cortada (de la cintura para arriba) y va pegada abajo.
    y = alto_c - fig.height if apoyo == "borde" else round(PIE_Y * alto_c - fig.height)
    compuesto = fondo.copy()
    compuesto.paste(fig, (x, y), fig)
    alfa = Image.new("L", (ancho_c, alto_c), 0)
    alfa.paste(fig.getchannel("A"), (x, y))
    return compuesto, alfa, (x, y, x + fig.width, y + fig.height)


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


def mascara(alfa: Image.Image, caja, dilatacion: float, corrimiento: float) -> Image.Image:
    """Alfa binarizado y dilatado + una elipse de sombra al pie de la figura."""
    ancho_c, alto_c = alfa.size
    m = dilatar(alfa.point(lambda v: 255 if v > 32 else 0), round(dilatacion * alto_c))
    x0, _, x1, y1 = caja
    ancho = x1 - x0
    cx = (x0 + x1) / 2 + corrimiento * ancho
    alto = FRANJA_ALTO * alto_c
    d = ImageDraw.Draw(m)
    d.ellipse((cx - 0.75 * ancho, y1 - alto * 0.6, cx + 0.75 * ancho, y1 + alto * 0.4), fill=255)
    return m


def zona(mascaras: list[Image.Image]) -> tuple[int, int, int, int]:
    """La caja que contiene todas las máscaras, con margen, dentro del cuadro."""
    ancho_c, alto_c = mascaras[0].size
    union = mascaras[0]
    for m in mascaras[1:]:
        union = ImageChops.lighter(union, m)
    x0, y0, x1, y1 = union.getbbox()
    mg = round(MARGEN * alto_c)
    return max(0, x0 - mg), max(0, y0 - mg), min(ancho_c, x1 + mg), min(alto_c, y1 + mg)


def pegar(
    compuesto: Image.Image, editado_zona: Image.Image, caja_zona, m: Image.Image
) -> Image.Image:
    """Lo editado entra solo dentro de la máscara, con el borde difuminado HACIA ADENTRO (fuera
    de la máscara queda el compuesto, idéntico)."""
    editado = compuesto.copy()
    x0, y0, x1, y1 = caja_zona
    editado.paste(editado_zona.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS), (x0, y0))
    suave = erosionar(m, BORDE).filter(ImageFilter.GaussianBlur(BORDE / 2))
    suave = ImageChops.multiply(suave, m)  # nunca fuera de la máscara
    return Image.composite(editado, compuesto, suave)


def fuera_de_mascara(a: Image.Image, b: Image.Image, m: Image.Image) -> float:
    """Diferencia media (0–255) fuera de la máscara. Tiene que dar 0."""
    afuera = ImageChops.invert(m.point(lambda v: 255 if v > 0 else 0))
    dif = ImageChops.difference(a, b).convert("L")
    st = ImageStat.Stat(dif, afuera)
    return round(st.mean[0], 3)


def cambio_de_figura(compuesto: Image.Image, fundido: Image.Image, alfa: Image.Image) -> float:
    """Cuánto cambiaron los BORDES dentro de la figura (0–255): un número alto = Qwen cambió
    la forma, no solo la luz. Base del umbral de la revisión."""
    e1 = compuesto.convert("L").filter(ImageFilter.FIND_EDGES)
    e2 = fundido.convert("L").filter(ImageFilter.FIND_EDGES)
    dentro = alfa.point(lambda v: 255 if v > 128 else 0)
    return round(ImageStat.Stat(ImageChops.difference(e1, e2), dentro).mean[0], 2)


# ── la corrida ───────────────────────────────────────────────────────────────────
async def main(semillas: list[int]) -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas: dict = {}
    async with Comfy() as c:
        await c.liberar()
        for k, e in ESCENAS.items():
            compuesto, alfa, caja = componer(e["escena"], e["figura"], e["apoyo"])
            compuesto.save(SALIDAS / f"{k}_tosco.png")
            alfa.save(SALIDAS / f"{k}_alfa.png")
            mascaras = {
                (dn, fn): mascara(alfa, caja, dv, fv)
                for dn, dv in DILATACIONES.items()
                for fn, fv in FRANJAS.items()
            }
            for (dn, fn), m in mascaras.items():
                m.save(SALIDAS / f"{k}_mascara_{dn}_{fn}.png")
            caja_zona = zona(list(mascaras.values()))
            compuesto.crop(caja_zona).save(SALIDAS / f"{k}_zona.png")
            sub_zona = await c.subir(SALIDAS / f"{k}_zona.png")
            sub_todo = await c.subir(SALIDAS / f"{k}_tosco.png")
            medidas[k] = {"caja_figura": caja, "caja_zona": caja_zona}
            for s in semillas:
                for camino, sub in (("zona", sub_zona), ("global", sub_todo)):
                    clave = f"{k}_{camino}_s{s}"
                    try:
                        r = await c.correr(grafo_qwen(sub, PROMPT_FUNDIR, s, f"spec790/e4/{clave}"))
                    except ComfyError as err:
                        medidas[clave] = {"error": str(err), "detalle": err.detalle[:400]}
                        print(clave, "ERROR", err, flush=True)
                        continue
                    crudo = SALIDAS / f"{clave}_qwen.png"
                    await c.bajar(r.imagenes[0], crudo)
                    medidas[clave] = {"segundos": r.segundos, "vram_pico_mb": r.vram_pico_mb}
                    salida = Image.open(crudo).convert("RGB")
                    if camino == "global":
                        g = salida.resize(compuesto.size, Image.Resampling.LANCZOS)
                        g.save(SALIDAS / f"{clave}.png")
                        medidas[clave]["fondo_cambiado"] = fuera_de_mascara(
                            g, compuesto, mascaras[("d4", "abajo_derecha")]
                        )
                    else:
                        for (dn, fn), m in mascaras.items():
                            f = pegar(compuesto, salida, caja_zona, m)
                            f.save(SALIDAS / f"{k}_{dn}_{fn}_s{s}.png")
                            medidas[clave][f"{dn}_{fn}"] = {
                                "fuera_de_mascara": fuera_de_mascara(f, compuesto, m),
                                "cambio_figura": cambio_de_figura(compuesto, f, alfa),
                            }
                    print(clave, json.dumps(medidas[clave])[:300], flush=True)
                    (SALIDAS / "medidas.json").write_text(json.dumps(medidas, indent=2))
        await c.liberar()
    return medidas


def grillas(semillas: list[int]) -> None:
    for k in ESCENAS:
        filas = [
            (
                "máscaras",
                [("compuesto tosco", SALIDAS / f"{k}_tosco.png")]
                + [
                    (f"{dn} {fn}", SALIDAS / f"{k}_mascara_{dn}_{fn}.png")
                    for dn in DILATACIONES
                    for fn in FRANJAS
                ][:5],
            )
        ]
        for s in semillas:
            celdas = [
                ("tosco", SALIDAS / f"{k}_tosco.png"),
                ("global (control)", SALIDAS / f"{k}_global_s{s}.png"),
            ]
            celdas += [
                (f"{dn} {fn}", SALIDAS / f"{k}_{dn}_{fn}_s{s}.png")
                for dn in DILATACIONES
                for fn in FRANJAS
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
