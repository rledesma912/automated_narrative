"""Spike E3b (Spec-790 §10.0, pedido de Yael tras E3): los escenarios salen «cartoon lúgubre»
(estilo Coraline). El boceto es la guía de qué va y dónde; la imagen tiene que ser una FOTO
REAL de noche: una mansión real, árboles reales, una caseta real. Nada de render.

Parte de las salidas `qwen_b` de E3 (e3/salidas/<boceto>_qwen_b_s<semilla>.png) y prueba:
  qwen_foto  Qwen-Edit en un paso, prompt de foto real (cámara, lente, materiales), sin las
             palabras del arte que estilizan («cinematic», «being watched»…)
  zimg_45 / zimg_60  qwen_b → Z-Image Turbo img2img, denoise 0,45 / 0,60 (Z-Image es muy
             fotográfico: le pone materiales reales y conserva el encuadre)
  zcn_gris   qwen_b → Z-Image + Fun ControlNet lite (control «gray» con la salida de Qwen),
             fuerza 0,6: Z-Image pinta de cero siguiendo la estructura
  qwen_x2    qwen_b → segunda pasada de Qwen-Edit: «convertí esta imagen en una foto real»

    uv run python e3b_realista.py [--variantes …] [--semillas 11,22,33]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, INSUMOS, Comfy, ComfyError, grilla  # noqa: E402
from e1_personaje import grafo_qwen, grafo_zcn, grafo_zimage  # noqa: E402
from e3_escenario import BOCETOS, VACIO  # noqa: E402

SALIDAS = AQUI / "e3b" / "salidas"
E3 = AQUI / "e3" / "salidas"

FOTO = (
    "A real, unedited photograph taken at night with a full-frame camera and a 35mm lens, "
    "black and white, lit only by moonlight, deep shadows, low fog close to the ground. "
    "Realistic materials and textures: weathered wood, old stone and brick, real roof "
    "tiles, real pine needles and bark, real grass and dirt. Natural film grain, slight "
    "lens vignetting. It must look like a real place photographed by a person: not an "
    "illustration, not a drawing, not a painting, not a cartoon, not a 3D render, not CGI, "
    "not stylized, not a movie poster."
)


def prompt_foto_desde_boceto(desc: str) -> str:
    return (
        "Turn this rough pencil sketch into a real photograph of the same place, keeping "
        "exactly the composition, the perspective, the layout and the position and size of "
        f"every element of the sketch. {desc} {FOTO} {VACIO} No pencil lines, no text."
    )


def prompt_foto_desde_imagen() -> str:
    return (
        "Make this image a real photograph. Keep exactly the same composition, the same "
        "buildings, trees and objects in the same places and sizes, the same moonlight and "
        f"the same black and white night look. {FOTO} {VACIO} No text."
    )


def prompt_zimage(desc: str) -> str:
    return f"{FOTO} {desc} {VACIO}"


VARIANTES = {
    # (boceto subido, imagen de qwen_b subida, datos del boceto, semilla, prefijo) → grafo
    "qwen_foto": lambda bo, _q, b, s, p: grafo_qwen(
        bo, prompt_foto_desde_boceto(b["descripcion"]), s, p
    ),
    "zimg_45": lambda _bo, q, b, s, p: grafo_zimage(prompt_zimage(b["descripcion"]), s, p, q, 0.45),
    "zimg_60": lambda _bo, q, b, s, p: grafo_zimage(prompt_zimage(b["descripcion"]), s, p, q, 0.60),
    "zcn_gris": lambda _bo, q, b, s, p: grafo_zcn(
        prompt_zimage(b["descripcion"]), s, p, q, "lite", 0.6
    ),
    "qwen_x2": lambda _bo, q, _b, s, p: grafo_qwen(q, prompt_foto_desde_imagen(), s, p),
}
MODELO = {"qwen_foto": "qwen", "qwen_x2": "qwen", "zimg_45": "zimage", "zimg_60": "zimage"}
MODELO["zcn_gris"] = "zcn"


async def main(variantes: list[str], semillas: list[int]) -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas_ruta = SALIDAS / "medidas.json"
    medidas = json.loads(medidas_ruta.read_text()) if medidas_ruta.exists() else {}
    async with Comfy() as c:
        bocetos = {k: await c.subir(INSUMOS / "bocetos" / b["archivo"]) for k, b in BOCETOS.items()}
        qwen_b = {
            (k, s): await c.subir(E3 / f"{k}_qwen_b_s{s}.png") for k in BOCETOS for s in semillas
        }
        modelo_cargado = None
        for v in variantes:
            if MODELO[v] != modelo_cargado:
                await c.liberar()
                await asyncio.sleep(2)
                modelo_cargado = MODELO[v]
            for k, b in BOCETOS.items():
                for s in semillas:
                    clave = f"{k}_{v}_s{s}"
                    grafo = VARIANTES[v](bocetos[k], qwen_b[(k, s)], b, s, f"spec790/e3b/{clave}")
                    try:
                        r = await c.correr(grafo)
                    except ComfyError as e:
                        medidas[clave] = {"error": str(e), "detalle": e.detalle[:500]}
                        print(clave, "ERROR", e, e.detalle[:200], flush=True)
                        continue
                    await c.bajar(r.imagenes[0], SALIDAS / f"{clave}.png")
                    medidas[clave] = {"segundos": r.segundos, "vram_pico_mb": r.vram_pico_mb}
                    print(clave, medidas[clave], flush=True)
                    medidas_ruta.write_text(json.dumps(medidas, indent=2))
        await c.liberar()
    return medidas


def grillas(semillas: list[int]) -> None:
    for k, b in BOCETOS.items():
        boceto = INSUMOS / "bocetos" / b["archivo"]
        filas = [
            (
                "qwen_b (E3)",
                [("boceto", boceto)] + [(f"s{s}", E3 / f"{k}_qwen_b_s{s}.png") for s in semillas],
            )
        ]
        for v in VARIANTES:
            celdas = [("boceto", boceto)] + [
                (f"s{s}", SALIDAS / f"{k}_{v}_s{s}.png")
                for s in semillas
                if (SALIDAS / f"{k}_{v}_s{s}.png").exists()
            ]
            if len(celdas) > 1:
                filas.append((v, celdas))
        print(grilla(filas, SALIDAS / f"grilla_{k}.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variantes", default=",".join(VARIANTES))
    ap.add_argument("--semillas", default="11,22,33")
    ap.add_argument("--solo-grilla", action="store_true")
    a = ap.parse_args()
    sem = [int(x) for x in a.semillas.split(",")]
    if not a.solo_grilla:
        asyncio.run(main(a.variantes.split(","), sem))
    grillas(sem)
