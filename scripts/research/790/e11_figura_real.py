"""Spike E11 (Spec-790 T6.3): el personaje de `qwen_b` sale como render 3D de videojuego, no
como foto. ¿Se lo puede llevar a foto (flash, cámara trampa) sin perder la forma NO humana del
boceto? Riesgo: que el modelo lo humanice.

Variantes (fondo gris, como la pieza del arnés):
  base           qwen_b como hoy (config/miniatura/prompts/personaje.md)
  foto_35/45/55  base → Z-Image img2img con prompt de foto con flash, denoise 0,35/0,45/0,55
  qwen_foto      el prompt de Qwen en clave foto con flash (sin «cinematic» ni luz de estudio)
  qwen_foto_z45  qwen_foto → Z-Image img2img 0,45

    uv run python e11_figura_real.py [--variantes …] [--semillas 11,22,33] [--solo-grilla]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, INSUMOS, Comfy, ComfyError, grilla  # noqa: E402
from e1_personaje import grafo_qwen, grafo_zimage  # noqa: E402

SALIDAS = AQUI / "e11" / "salidas"
RAIZ = AQUI.parents[2]
PERSONAJE_MD = (RAIZ / "config/miniatura/prompts/personaje.md").read_text(encoding="utf-8").strip()

BOCETOS = {
    # La descripción tal como la cargó Yael (llega en castellano al prompt, como en el arnés).
    "peter": {
        "archivo": "peter_personaje.png",
        "descripcion": "Una criatura de piel oscura, muy alta, esbelta y robusta, con ojos "
        "amarillos, desorbitados, que brillan en la oscuridad y están sobresalidos. De figura "
        "humanoide, pero no es humano, Tiene dos orejitas pequeñas como de animal, una nariz "
        "larga y picuda, y una boca sonriente llena de dientes afilados. Está semi escondido "
        "detrás de un árbol. Hiperrealista, debe parecer una foto real.",
    },
    "torre": {
        "archivo": "torre_personaje.png",
        "descripcion": "An impossibly tall, emaciated humanoid creature of flesh and grey "
        "skin: a small bald head with two large empty glowing white eyes and no mouth, "
        "thin grey skin stretched tight over the ribs of a starved body, extremely long "
        "thin arms hanging below the knees ending in long bony fingers, long thin legs and "
        "long toes, standing upright facing the viewer. A living creature, not a skeleton.",
    },
}

# Z-Image sobre la figura ya hecha: cambiar el material, no la forma.
FOTO_Z = (
    "A real, unedited flash photograph of a real living creature, taken at night with a "
    "cheap camera and a harsh direct on-camera flash, like a trail camera or a found-footage "
    "photo. {descripcion} Its body is not human: it keeps exactly its shape, its proportions, "
    "its head, ears, mouth, teeth and claws. Real organic skin with pores, wrinkles, veins, "
    "wet patches, scars and dirt, flat harsh flash light on the front, the edges falling into "
    "shadow. Grainy, a little blurry, low quality amateur photo. Not a 3D render, not CGI, "
    "not a video game, not a toy, not a sculpture. Plain flat medium grey background, "
    "nothing else."
)

QWEN_FOTO = (
    "Turn this rough pencil sketch into a real flash photograph of the same creature, "
    "keeping exactly the pose, the proportions, the silhouette, the position in the frame "
    "and every non-human feature of the sketch: the head, the ears, the mouth and teeth, "
    "the hands and claws. {descripcion} It is a real living creature photographed at night "
    "with a harsh direct camera flash from the front, like a trail camera or a found-footage "
    "photo: real organic skin with pores, wrinkles, veins, wet patches and dirt, flat flash "
    "light, the edges falling into shadow, slightly blurry, heavy grain, low quality amateur "
    "photo. Muted desaturated colors. Not a 3D render, not CGI, not a video game character, "
    "not a cartoon, not a painting. Plain flat uniform medium grey background, no scenery, "
    "no floor, no objects. No pencil lines, no text."
)

VARIANTES = ["base", "foto_35", "foto_45", "foto_55", "qwen_foto", "qwen_foto_z45"]
DE_Z = {"foto_35": ("base", 0.35), "foto_45": ("base", 0.45), "foto_55": ("base", 0.55),
        "qwen_foto_z45": ("qwen_foto", 0.45)}


async def main(variantes: list[str], semillas: list[int]) -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas_ruta = SALIDAS / "medidas.json"
    medidas = json.loads(medidas_ruta.read_text()) if medidas_ruta.exists() else {}

    async def guardar(clave, r, destino):
        await c.bajar(r.imagenes[0], destino)
        medidas[clave] = {"segundos": r.segundos, "vram_pico_mb": r.vram_pico_mb}
        print(clave, medidas[clave], flush=True)
        medidas_ruta.write_text(json.dumps(medidas, indent=2))

    async with Comfy() as c:
        bocetos = {k: await c.subir(INSUMOS / "bocetos" / b["archivo"]) for k, b in BOCETOS.items()}
        # Primero todo lo de Qwen (un modelo cargado), después todo lo de Z-Image.
        for v in [v for v in ("base", "qwen_foto") if v in variantes or any(
                DE_Z.get(x, ("",))[0] == v for x in variantes)]:
            plantilla = PERSONAJE_MD if v == "base" else QWEN_FOTO
            for k, b in BOCETOS.items():
                for s in semillas:
                    clave = f"{k}_{v}_s{s}"
                    destino = SALIDAS / f"{clave}.png"
                    if destino.exists():
                        continue
                    prompt = plantilla.replace("{descripcion}", b["descripcion"])
                    try:
                        r = await c.correr(grafo_qwen(bocetos[k], prompt, s, f"spec790/e11/{clave}"))
                    except ComfyError as e:
                        print(clave, "ERROR", e, e.detalle[:300], flush=True)
                        continue
                    await guardar(clave, r, destino)
        await c.liberar()
        for v in [v for v in variantes if v in DE_Z]:
            fuente, denoise = DE_Z[v]
            for k, b in BOCETOS.items():
                for s in semillas:
                    clave = f"{k}_{v}_s{s}"
                    destino = SALIDAS / f"{clave}.png"
                    origen = SALIDAS / f"{k}_{fuente}_s{s}.png"
                    if destino.exists() or not origen.exists():
                        continue
                    subida = await c.subir(origen)
                    prompt = FOTO_Z.replace("{descripcion}", b["descripcion"])
                    try:
                        r = await c.correr(
                            grafo_zimage(prompt, s, f"spec790/e11/{clave}", subida, denoise)
                        )
                    except ComfyError as e:
                        print(clave, "ERROR", e, e.detalle[:300], flush=True)
                        continue
                    await guardar(clave, r, destino)
        await c.liberar()
    return medidas


def grillas(semillas: list[int]) -> None:
    for k, b in BOCETOS.items():
        boceto = INSUMOS / "bocetos" / b["archivo"]
        filas = []
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
