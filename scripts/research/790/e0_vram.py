"""Spike E0, parte 2: con un modelo de verdad (Z-Image Turbo fp8 AIO, del workflow «5a» del
usuario), ¿cuánto pesa en VRAM, cuánto tarda en frío y en caliente, y /free la devuelve?

    uv run python e0_vram.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import Comfy  # noqa: E402

PROMPT = (
    "Dark horror night photograph, black and white, an empty dirt road in a small town, "
    "low fog, a single street lamp, heavy film grain, strong dark vignette"
)


def grafo_zimage(semilla: int, ancho: int = 1344, alto: int = 768) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "z-image-turbo-fp8-aio.safetensors"}},
        "2": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": PROMPT}},
        "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["3", 0]}},
        "5": {"class_type": "EmptySD3LatentImage", "inputs": {"width": ancho, "height": alto, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["2", 0], "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0],
            "seed": semilla, "steps": 5, "cfg": 1, "sampler_name": "dpmpp_sde", "scheduler": "beta", "denoise": 1}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": f"spec790/e0_zimage_{semilla}"}},
    }


async def main() -> dict:
    res = {}
    async with Comfy() as c:
        await c.liberar()
        await asyncio.sleep(2)
        res["vram_libre_inicio_mb"] = round(await c.vram_libre_mb())
        for etiqueta, semilla in [("frio", 101), ("caliente_1", 102), ("caliente_2", 103)]:
            r = await c.correr(grafo_zimage(semilla))
            await c.bajar(r.imagenes[0], Path(f"e0/salidas/zimage_{etiqueta}.png"))
            res[etiqueta] = {"segundos": r.segundos, "vram_pico_mb": r.vram_pico_mb, "via": r.via}
        res["vram_libre_con_modelo_mb"] = round(await c.vram_libre_mb())
        t = time.monotonic()
        await c.liberar()
        await asyncio.sleep(2)
        res["free_segundos"] = round(time.monotonic() - t - 2, 2)
        res["vram_libre_despues_de_free_mb"] = round(await c.vram_libre_mb())
    return res


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main()), ensure_ascii=False, indent=2))
