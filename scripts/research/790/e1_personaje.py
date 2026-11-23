"""Spike E1 (Spec-790 §10.0): ¿un boceto de Yael se vuelve un personaje terminado, con el arte
del canal, reconocible como su dibujo? Siempre sobre fondo liso (después se recorta, E2).

Variantes con lo que ya está instalado (las que piden bajar modelos esperan el OK):
  qwen_a  Qwen-Edit 2511 + Lightning, instrucción corta («convertí el boceto…»)
  qwen_b  Qwen-Edit 2511 + Lightning, instrucción larga (arte completo de arte.yaml)
  zimg_75 / zimg_90  Z-Image Turbo img2img desde el boceto, denoise 0,75 y 0,90
  ztxt    Z-Image Turbo solo desde el texto (el control: sin boceto)
  zcn_{full,lite}_{70,90}  Z-Image Turbo + Fun ControlNet Union 2.1 (2602, 8 pasos), el boceto
          pasado a scribble por Python (líneas blancas sobre negro), fuerza 0,7 y 0,9

    uv run python e1_personaje.py [--variantes qwen_a,ztxt] [--semillas 11,22,33]

Deja las imágenes en e1/salidas/, los tiempos y la VRAM en e1/salidas/medidas.json y una grilla
por boceto (fila = variante, celda = semilla, la primera celda es el boceto).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, INSUMOS, Comfy, ComfyError, grilla  # noqa: E402

SALIDAS = AQUI / "e1" / "salidas"

# El arte, tal como está en el borrador de arte.yaml (§2.2). Para el personaje no va el
# escenario: fondo liso, para recortar.
ARTE = {
    "estilo": "Dark horror night photograph, photorealistic, black and white or heavily "
    "desaturated, cinematic, looks like a real photo taken at night, not a painting, "
    "not a cartoon.",
    "luz": "A single hard light source, deep crushed blacks, the figure partly lit and "
    "partly in shadow.",
    "textura": "Heavy film grain, dirty scratched texture.",
    "negativos": "text, letters, watermark, logo, saturated colors, gore, blood, extra "
    "limbs, extra fingers, cartoon, painting, illustration, pencil lines, sketch, "
    "bright daylight, scenery, background objects",
}
FONDO = (
    "Plain flat uniform medium grey studio background, no scenery, no floor, no objects, "
    "the whole figure visible from head to the bottom of the frame."
)

# La descripción editable que propondría la IA desde el relato (paso 1 del flujo).
BOCETOS = {
    "torre": {
        "archivo": "torre_personaje.png",
        "descripcion": "An impossibly tall, gaunt humanoid creature: a small bald head with "
        "two large empty glowing white eyes and no mouth, a skeletal torso with visible "
        "ribs, extremely long thin arms hanging below the knees ending in long bony "
        "fingers, long thin legs and long toes, standing upright facing the viewer.",
    },
    # La misma criatura sin «skeletal» ni «visible ribs», que llevaban a un esqueleto de render.
    "torre_piel": {
        "archivo": "torre_personaje.png",
        "descripcion": "An impossibly tall, emaciated humanoid creature of flesh and grey "
        "skin: a small bald head with two large empty glowing white eyes and no mouth, "
        "thin grey skin stretched tight over the ribs of a starved body, extremely long "
        "thin arms hanging below the knees ending in long bony fingers, long thin legs and "
        "long toes, standing upright facing the viewer. A living creature, not a skeleton.",
    },
    "mansion": {
        "archivo": "mansion_personaje.png",
        "descripcion": "A little girl wearing a worn, cracked white rabbit mask with long "
        "ears and big black hollow eyes, long straight black hair, an old stained dress "
        "with puffed sleeves, holding in front of her a carved jack-o'-lantern pumpkin with "
        "an evil grin, seen from the waist up.",
    },
}


def prompt_qwen_corto(desc: str) -> str:
    return (
        "Turn this rough pencil sketch into a finished photorealistic black and white "
        f"night photograph of the same character. {desc} Keep exactly the pose, the "
        "proportions, the silhouette and the position in the frame of the sketch. "
        f"{FONDO} No pencil lines left."
    )


def prompt_qwen_largo(desc: str) -> str:
    return (
        "Turn this rough pencil sketch into a finished image of the same character, "
        "keeping exactly the pose, the proportions, the silhouette and the position in "
        f"the frame of the sketch. {desc} {ARTE['estilo']} {ARTE['luz']} "
        f"{ARTE['textura']} {FONDO} No pencil lines, no text."
    )


def prompt_zimage(desc: str) -> str:
    return f"{ARTE['estilo']} {desc} {ARTE['luz']} {ARTE['textura']} {FONDO}"


# ── grafos ───────────────────────────────────────────────────────────────────
def grafo_qwen(imagen: str, prompt: str, semilla: int, prefijo: str) -> dict:
    """La plantilla de Qwen-Image-Edit 2511 + Lightning 4 pasos (la de cw2d-art)."""
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "qwen_image_edit_2511_int8_convrot.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image"},
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "6": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
                "strength_model": 1.0,
            },
        },
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["6", 0], "shift": 3.1}},
        "5": {"class_type": "CFGNorm", "inputs": {"model": ["4", 0], "strength": 1.0}},
        "7": {"class_type": "LoadImage", "inputs": {"image": imagen}},
        "8": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["7", 0]}},
        "9": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {"clip": ["2", 0], "prompt": prompt, "vae": ["3", 0], "image1": ["8", 0]},
        },
        "10": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {"clip": ["2", 0], "prompt": "", "vae": ["3", 0], "image1": ["8", 0]},
        },
        "11": {
            "class_type": "FluxKontextMultiReferenceLatentMethod",
            "inputs": {"conditioning": ["9", 0], "reference_latents_method": "index_timestep_zero"},
        },
        "12": {
            "class_type": "FluxKontextMultiReferenceLatentMethod",
            "inputs": {
                "conditioning": ["10", 0],
                "reference_latents_method": "index_timestep_zero",
            },
        },
        "13": {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["3", 0]}},
        "14": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "positive": ["11", 0],
                "negative": ["12", 0],
                "latent_image": ["13", 0],
                "seed": semilla,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["3", 0]}},
        "16": {
            "class_type": "SaveImage",
            "inputs": {"images": ["15", 0], "filename_prefix": prefijo},
        },
    }


def grafo_zimage(
    prompt: str, semilla: int, prefijo: str, imagen: str | None = None, denoise: float = 1.0
) -> dict:
    """Z-Image Turbo (AIO fp8, como E0). Con `imagen`, img2img desde el boceto."""
    g = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "z-image-turbo-fp8-aio.safetensors"},
        },
        "2": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["3", 0]}},
        "5": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": 1344, "height": 768, "batch_size": 1},
        },
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["2", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
                "seed": semilla,
                "steps": 8 if imagen else 5,
                "cfg": 1,
                "sampler_name": "dpmpp_sde",
                "scheduler": "beta",
                "denoise": denoise,
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {
            "class_type": "SaveImage",
            "inputs": {"images": ["7", 0], "filename_prefix": prefijo},
        },
    }
    if imagen:
        g["9"] = {"class_type": "LoadImage", "inputs": {"image": imagen}}
        g["10"] = {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["9", 0],
                "upscale_method": "lanczos",
                "width": 1344,
                "height": 768,
                "crop": "center",
            },
        }
        g["11"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["1", 2]}}
        g["6"]["inputs"]["latent_image"] = ["11", 0]
    return g


CN = {
    "full": "Z-Image-Turbo-Fun-Controlnet-Union-2.1-2602-8steps.safetensors",
    "lite": "Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-2602-8steps.safetensors",
}


def scribble(boceto: Path, destino: Path) -> Path:
    """El boceto de Yael (líneas oscuras sobre un fondo cualquiera, gris en SAI2) → líneas
    blancas sobre negro, como las imágenes de control scribble/HED. Sin IA."""
    from PIL import Image, ImageOps, ImageStat

    gris = ImageOps.grayscale(Image.open(boceto))
    fondo = ImageStat.Stat(gris).median[0]  # la mediana = el fondo (casi todo el lienzo)
    inv = gris.point(lambda v: max(0, min(255, int((fondo - v) * 255 / max(fondo - 20, 1)))))
    destino.parent.mkdir(parents=True, exist_ok=True)
    inv.convert("RGB").save(destino)
    return destino


def grafo_zcn(
    prompt: str, semilla: int, prefijo: str, control: str, cn: str, fuerza: float
) -> dict:
    """Z-Image Turbo + Fun ControlNet Union (model patch) con el boceto como scribble."""
    g = grafo_zimage(prompt, semilla, prefijo)
    g["20"] = {"class_type": "ModelPatchLoader", "inputs": {"name": CN[cn]}}
    g["21"] = {"class_type": "LoadImage", "inputs": {"image": control}}
    g["22"] = {
        "class_type": "ImageScale",
        "inputs": {
            "image": ["21", 0],
            "upscale_method": "lanczos",
            "width": 1344,
            "height": 768,
            "crop": "center",
        },
    }
    g["23"] = {
        "class_type": "ZImageFunControlnet",
        "inputs": {
            "model": ["1", 0],
            "model_patch": ["20", 0],
            "vae": ["1", 2],
            "strength": fuerza,
            "image": ["22", 0],
        },
    }
    g["2"]["inputs"]["model"] = ["23", 0]
    g["6"]["inputs"]["steps"] = 8
    return g


# Agrupadas por modelo: /free solo al cambiar de modelo (cargar Qwen tarda).
VARIANTES = {
    "qwen_a": lambda im, b, s, p: grafo_qwen(im, prompt_qwen_corto(b["descripcion"]), s, p),
    "qwen_b": lambda im, b, s, p: grafo_qwen(im, prompt_qwen_largo(b["descripcion"]), s, p),
    "zimg_75": lambda im, b, s, p: grafo_zimage(prompt_zimage(b["descripcion"]), s, p, im, 0.75),
    "zimg_90": lambda im, b, s, p: grafo_zimage(prompt_zimage(b["descripcion"]), s, p, im, 0.90),
    "ztxt": lambda _im, b, s, p: grafo_zimage(prompt_zimage(b["descripcion"]), s, p),
}
for _cn in CN:
    for _f in (70, 90):
        VARIANTES[f"zcn_{_cn}_{_f}"] = lambda _im, b, s, p, cn=_cn, f=_f: grafo_zcn(
            prompt_zimage(b["descripcion"]), s, p, b["control"], cn, f / 100
        )
MODELO = {
    v: "qwen" if v.startswith("qwen") else v.rsplit("_", 1)[0] if v.startswith("zcn") else "zimage"
    for v in VARIANTES
}


async def main(variantes: list[str], semillas: list[int], bocetos: list[str]) -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas_ruta = SALIDAS / "medidas.json"
    medidas = json.loads(medidas_ruta.read_text()) if medidas_ruta.exists() else {}
    async with Comfy() as c:
        elegidos = {k: BOCETOS[k] for k in bocetos}
        subidos = {
            k: await c.subir(INSUMOS / "bocetos" / b["archivo"]) for k, b in elegidos.items()
        }
        for k, b in elegidos.items():
            control = scribble(INSUMOS / "bocetos" / b["archivo"], SALIDAS / f"{k}_scribble.png")
            b["control"] = await c.subir(control)
        modelo_cargado = None
        for v in variantes:
            if MODELO[v] != modelo_cargado:
                await c.liberar()
                await asyncio.sleep(2)
                modelo_cargado = MODELO[v]
            for k, b in elegidos.items():
                for s in semillas:
                    clave = f"{k}_{v}_s{s}"
                    destino = SALIDAS / f"{clave}.png"
                    grafo = VARIANTES[v](subidos[k], b, s, f"spec790/e1/{clave}")
                    try:
                        r = await c.correr(grafo)
                    except ComfyError as e:
                        medidas[clave] = {"error": str(e), "detalle": e.detalle[:500]}
                        print(clave, "ERROR", e, e.detalle[:200], flush=True)
                        continue
                    await c.bajar(r.imagenes[0], destino)
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
            celdas = [("boceto", boceto)]
            celdas += [
                (f"s{s}", SALIDAS / f"{k}_{v}_s{s}.png")
                for s in semillas
                if (SALIDAS / f"{k}_{v}_s{s}.png").exists()
            ]
            if len(celdas) > 1:
                filas.append((v, celdas))
        if filas:
            print(grilla(filas, SALIDAS / f"grilla_{k}.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variantes", default=",".join(VARIANTES))
    ap.add_argument("--semillas", default="11,22,33")
    ap.add_argument("--bocetos", default="torre,mansion")
    ap.add_argument("--solo-grilla", action="store_true")
    a = ap.parse_args()
    sem = [int(x) for x in a.semillas.split(",")]
    if not a.solo_grilla:
        asyncio.run(main(a.variantes.split(","), sem, a.bocetos.split(",")))
    grillas(sem)
