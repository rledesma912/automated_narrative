"""Spike E3 (Spec-790 §10.0): ¿el boceto del escenario se vuelve un fondo 16:9 con el arte del
canal, reconocible como el dibujo de Yael? ¿Hace falta agrandar?

Variantes (reusan los grafos de E1):
  qwen_b       Qwen-Edit 2511 + Lightning, la ganadora de E1, a su resolución (~1392 × 752)
  qwen_b_1024  ídem a 1024 × 576, agrandada a 1280 × 720 en Python (Lanczos)
  zcn_lite_90  Z-Image Turbo + Fun ControlNet lite, fuerza 0,9 (en escenarios la silueta
               puede pesar más que el detalle)

    uv run python e3_escenario.py [--variantes …] [--semillas 11,22,33]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, INSUMOS, Comfy, ComfyError, grilla  # noqa: E402
from e1_personaje import grafo_qwen, grafo_zcn, scribble  # noqa: E402

SALIDAS = AQUI / "e3" / "salidas"

# arte.yaml (§2.2): estilo, luz, sentidos y textura. El escenario va vacío: el personaje se
# suma después (E4).
ARTE = (
    "Dark horror night photograph, photorealistic, black and white or heavily desaturated, "
    "cinematic, looks like a real photo taken at night, not a painting, not a cartoon. "
    "A single hard light source (moonlight), deep crushed blacks, most of the frame in "
    "shadow. Cold damp night air, low fog close to the ground, dead silence, the feeling of "
    "being watched from the dark. Heavy film grain, strong dark vignette on all edges, "
    "dirty scratched texture."
)
VACIO = "Nobody in the scene: no people, no creatures, no animals."

BOCETOS = {
    "torre": {
        "archivo": "torre_escenario.png",
        "descripcion": "A dense pine forest at night seen from just above the treetops, "
        "a tall wooden fire lookout tower on four long legs rising among the trees on the "
        "right, its small cabin with a pointed roof, a narrow balcony and dark windows, a "
        "faint light around the cabin, mountains far behind under the night sky.",
    },
    "mansion": {
        "archivo": "mansion_escenario.png",
        "descripcion": "A large old Victorian mansion seen from the front: pointed towers, "
        "tiled roofs and chimneys, balconies with iron railings, rows of arched windows, a "
        "dark front door at the top of wide stone stairs, two lit candles and two carved "
        "jack-o'-lanterns at the foot of the stairs, a winding dirt path leading to the "
        "stairs, big bare trees on the left and a row of tall poplar trees on the right.",
    },
}


def prompt_qwen(desc: str) -> str:
    return (
        "Turn this rough pencil sketch into a finished image of the same place, keeping "
        "exactly the composition, the perspective, the layout and the position and size of "
        f"every element of the sketch. {desc} {ARTE} {VACIO} No pencil lines, no text."
    )


def prompt_zimage(desc: str) -> str:
    return f"{ARTE} {desc} {VACIO}"


def grafo_qwen_1024(imagen: str, prompt: str, semilla: int, prefijo: str) -> dict:
    """La ganadora de E1, pero a 1024 × 576 en vez del tamaño que elige FluxKontextImageScale."""
    g = grafo_qwen(imagen, prompt, semilla, prefijo)
    g["8"] = {
        "class_type": "ImageScale",
        "inputs": {
            "image": ["7", 0],
            "upscale_method": "lanczos",
            "width": 1024,
            "height": 576,
            "crop": "center",
        },
    }
    return g


VARIANTES = {
    "qwen_b": lambda im, b, s, p: grafo_qwen(im, prompt_qwen(b["descripcion"]), s, p),
    "qwen_b_1024": lambda im, b, s, p: grafo_qwen_1024(im, prompt_qwen(b["descripcion"]), s, p),
    "zcn_lite_90": lambda _im, b, s, p: grafo_zcn(
        prompt_zimage(b["descripcion"]), s, p, b["control"], "lite", 0.9
    ),
}
MODELO = {"qwen_b": "qwen", "qwen_b_1024": "qwen", "zcn_lite_90": "zcn"}


def agrandar(ruta: Path) -> Path:
    """1024 × 576 → 1280 × 720 con Lanczos (el tamaño final de la miniatura)."""
    from PIL import Image

    destino = ruta.with_name(ruta.stem + "_1280.png")
    Image.open(ruta).resize((1280, 720), Image.Resampling.LANCZOS).save(destino)
    return destino


async def main(variantes: list[str], semillas: list[int]) -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas_ruta = SALIDAS / "medidas.json"
    medidas = json.loads(medidas_ruta.read_text()) if medidas_ruta.exists() else {}
    async with Comfy() as c:
        subidos = {}
        for k, b in BOCETOS.items():
            subidos[k] = await c.subir(INSUMOS / "bocetos" / b["archivo"])
            control = scribble(INSUMOS / "bocetos" / b["archivo"], SALIDAS / f"{k}_scribble.png")
            b["control"] = await c.subir(control)
        modelo_cargado = None
        for v in variantes:
            if MODELO[v] != modelo_cargado:
                await c.liberar()
                await asyncio.sleep(2)
                modelo_cargado = MODELO[v]
            for k, b in BOCETOS.items():
                for s in semillas:
                    clave = f"{k}_{v}_s{s}"
                    destino = SALIDAS / f"{clave}.png"
                    try:
                        r = await c.correr(VARIANTES[v](subidos[k], b, s, f"spec790/e3/{clave}"))
                    except ComfyError as e:
                        medidas[clave] = {"error": str(e), "detalle": e.detalle[:500]}
                        print(clave, "ERROR", e, e.detalle[:200], flush=True)
                        continue
                    await c.bajar(r.imagenes[0], destino)
                    if v == "qwen_b_1024":
                        agrandar(destino)
                    medidas[clave] = {"segundos": r.segundos, "vram_pico_mb": r.vram_pico_mb}
                    print(clave, medidas[clave], flush=True)
                    medidas_ruta.write_text(json.dumps(medidas, indent=2))
        await c.liberar()
    return medidas


def grillas(semillas: list[int]) -> None:
    for k, b in BOCETOS.items():
        boceto = INSUMOS / "bocetos" / b["archivo"]
        filas = []
        for v in VARIANTES:
            sufijo = "_1280" if v == "qwen_b_1024" else ""
            celdas = [("boceto", boceto)] + [
                (f"s{s}", SALIDAS / f"{k}_{v}_s{s}{sufijo}.png")
                for s in semillas
                if (SALIDAS / f"{k}_{v}_s{s}{sufijo}.png").exists()
            ]
            if len(celdas) > 1:
                filas.append((v, celdas))
        if filas:
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
