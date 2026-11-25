"""Spike E11c-2: (a) prompt en positivo como lo escribiría un LLM; (b) negativo real en Z-Image
(cfg 1,5 / 2). Sobre el Qwen «nuevo» (sin persona) del escenario de Peter."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy, grilla  # noqa: E402
from e1_personaje import grafo_zimage  # noqa: E402
from e11c_escenario import BOCETO, DESC, SALIDAS  # noqa: E402

BASE = (AQUI / "e11c/fotografiar_nuevo.md").read_text().strip().replace("{descripcion}", DESC)
LLM = (
    "A real, unedited photograph taken on a very dark night with a full-frame camera and a 35mm "
    "lens, in muted desaturated colors with a cold blue-teal night tint, underexposed. A dense "
    "wild forest: tall dry dead trees and a few leafy ones, dark bushes and leafy plants in the "
    "foreground, tall wild grass, and thick whitish fog low between the trunks. Deep in the fog, "
    "only more trees fading into darkness. Faint diffuse moonglow through the fog, most of the "
    "image in deep darkness. Real bark, leaves, grass and wet dirt. Natural film grain. A real "
    "place photographed by a person, empty and lonely."
)
NEG = (
    "person, people, man, woman, child, figure, silhouette of a person, creature, animal, "
    "house, cabin, shed, hut, building, wall, fence, window, lit window, lamp, roof, boat, chair"
)
SEM = [990851, 11, 22]


def con_negativo(g: dict, cfg: float) -> dict:
    g["4"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": NEG}}
    g["6"]["inputs"]["cfg"] = cfg
    return g


async def main():
    async with Comfy() as c:
        for v, prompt, cfg in (("llm", LLM, None), ("neg15", BASE, 1.5), ("neg20", BASE, 2.0)):
            for s in SEM:
                d = SALIDAS / f"{v}_foto_s{s}.png"
                if d.exists():
                    continue
                sub = await c.subir(SALIDAS / f"nuevo_oscuro_s{s}.png")
                g = grafo_zimage(prompt, s, f"spec790/e11c/{v}_{s}", sub, 0.45)
                if cfg:
                    g = con_negativo(g, cfg)
                r = await c.correr(g)
                await c.bajar(r.imagenes[0], d)
                print(d.name, r.segundos, flush=True)
        await c.liberar()
    filas = [(v, [("boceto", BOCETO)] + [(f"s{s}", SALIDAS / f"{v}_foto_s{s}.png") for s in SEM])
             for v in ("nuevo", "salvaje", "llm", "neg15", "neg20")]
    print(grilla(filas, SALIDAS / "grilla_negativo.png"))


asyncio.run(main())
