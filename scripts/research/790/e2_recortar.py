"""Spike E2 (Spec-790 §10.0): ¿el recorte del personaje de E1 sale limpio (pelo, dedos, orejas,
bordes oscuros sobre el gris)?

Parte de las salidas `qwen_b` de E1 (el ganador, sobre fondo liso):
  a  BiRefNet (nodo propio de ComfyUI, `birefnet.safetensors`, MIT): la máscara tal cual
  b  BiRefNet + refinado en Python: solo la figura (sin islas sueltas), borde 1–2 px adentro
     (saca el halo gris del fondo) y difuminado suave

Cada recorte se mira sobre negro, sobre blanco y sobre un escenario oscuro de E3c (el uso real),
con un zoom al borde a 100 % y la miniatura a 120 px.

    uv run python e2_recortar.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy, grilla  # noqa: E402

SALIDAS = AQUI / "e2" / "salidas"
E1 = AQUI / "e1" / "salidas"
ESCENARIO = AQUI / "e3c" / "salidas" / "mansion_previo_45_s22.png"
PERSONAJES = [f"{k}_qwen_b_s{s}" for k in ("torre_piel", "mansion") for s in (11, 22, 33)]


def grafo_birefnet(imagen: str, prefijo: str) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": imagen}},
        "2": {
            "class_type": "LoadBackgroundRemovalModel",
            "inputs": {"bg_removal_name": "birefnet.safetensors"},
        },
        "3": {
            "class_type": "RemoveBackground",
            "inputs": {"bg_removal_model": ["2", 0], "image": ["1", 0]},
        },
        "4": {"class_type": "MaskToImage", "inputs": {"mask": ["3", 0]}},
        "5": {
            "class_type": "SaveImage",
            "inputs": {"images": ["4", 0], "filename_prefix": prefijo},
        },
    }


def refinar(mascara, erosion: int = 2, difuminado: float = 1.2, islas: int = 7):
    """Sin IA y solo con Pillow (sin dependencias nuevas): (1) apertura morfológica de la
    máscara binaria (borra manchitas sueltas de menos de ~`islas` px) y se usa como tope,
    (2) achica el borde `erosion` px (saca el halo gris del fondo), (3) difumina."""
    from PIL import ImageChops, ImageFilter

    m = mascara.convert("L")
    binaria = m.point(lambda v: 255 if v > 127 else 0)
    abierta = binaria.filter(ImageFilter.MinFilter(islas)).filter(ImageFilter.MaxFilter(islas))
    tope = abierta.filter(ImageFilter.MaxFilter(5))  # deja el borde suave pegado a la figura
    m = ImageChops.multiply(m, tope)
    if erosion:
        m = m.filter(ImageFilter.MinFilter(erosion * 2 + 1))
    if difuminado:
        m = m.filter(ImageFilter.GaussianBlur(difuminado))
    return m


def recorte(original: Path, mascara, destino: Path) -> Path:
    from PIL import Image

    im = Image.open(original).convert("RGB")
    rgba = im.copy()
    rgba.putalpha(mascara.resize(im.size))
    rgba.save(destino)
    return destino


def sobre(recorte_png: Path, fondo, destino: Path) -> Path:
    """El recorte pegado sobre un fondo (color o imagen), escalado al 85 % del alto."""
    from PIL import Image

    fig = Image.open(recorte_png)
    if isinstance(fondo, tuple):
        base = Image.new("RGB", fig.size, fondo)
    else:
        base = Image.open(fondo).convert("RGB").resize(fig.size)
    base.paste(fig, (0, 0), fig)
    base.save(destino)
    return destino


def zoom(imagen: Path, destino: Path, caja: tuple[float, float, float, float]) -> Path:
    """Un pedazo del borde a 100 % (caja en fracciones del ancho/alto), llevado a 16:9."""
    from PIL import Image

    im = Image.open(imagen)
    w, h = im.size
    x0, y0, x1, y1 = (int(caja[0] * w), int(caja[1] * h), int(caja[2] * w), int(caja[3] * h))
    im.crop((x0, y0, x1, y1)).save(destino)
    return destino


# Dónde mirar el borde: los dedos de la criatura y las orejas de la máscara.
ZOOM = {"torre_piel": (0.30, 0.50, 0.45, 0.85), "mansion": (0.36, 0.0, 0.62, 0.35)}


async def main() -> dict:
    from PIL import Image

    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas = {}
    async with Comfy() as c:
        await c.liberar()
        for p in PERSONAJES:
            subido = await c.subir(E1 / f"{p}.png")
            r = await c.correr(grafo_birefnet(subido, f"spec790/e2/{p}"))
            await c.bajar(r.imagenes[0], SALIDAS / f"{p}_mascara.png")
            medidas[p] = {"segundos": r.segundos, "vram_pico_mb": r.vram_pico_mb}
            print(p, medidas[p], flush=True)
        await c.liberar()
    (SALIDAS / "medidas.json").write_text(json.dumps(medidas, indent=2))

    for p in PERSONAJES:
        bruta = Image.open(SALIDAS / f"{p}_mascara.png").convert("L")
        for v, m in (("a", bruta), ("b", refinar(bruta))):
            rec = recorte(E1 / f"{p}.png", m, SALIDAS / f"{p}_{v}.png")
            sobre(rec, (0, 0, 0), SALIDAS / f"{p}_{v}_negro.png")
            sobre(rec, (255, 255, 255), SALIDAS / f"{p}_{v}_blanco.png")
            sobre(rec, ESCENARIO, SALIDAS / f"{p}_{v}_escena.png")
            zoom(
                SALIDAS / f"{p}_{v}_escena.png",
                SALIDAS / f"{p}_{v}_zoom.png",
                ZOOM[p.split("_qwen")[0]],
            )
    return medidas


def grillas() -> None:
    for k in ("torre_piel", "mansion"):
        filas = []
        for s in (11, 22, 33):
            p = f"{k}_qwen_b_s{s}"
            for v in ("a", "b"):
                filas.append(
                    (
                        f"s{s} {'BiRefNet' if v == 'a' else '+ refinado'}",
                        [
                            ("original", E1 / f"{p}.png"),
                            ("máscara", SALIDAS / f"{p}_mascara.png"),
                            ("sobre negro", SALIDAS / f"{p}_{v}_negro.png"),
                            ("sobre blanco", SALIDAS / f"{p}_{v}_blanco.png"),
                            ("sobre la escena", SALIDAS / f"{p}_{v}_escena.png"),
                            ("borde a 100 %", SALIDAS / f"{p}_{v}_zoom.png"),
                        ],
                    )
                )
        print(grilla(filas, SALIDAS / f"grilla_{k}.png", ancho_celda=320))


if __name__ == "__main__":
    if "--solo-grilla" not in sys.argv:
        asyncio.run(main())
    grillas()
