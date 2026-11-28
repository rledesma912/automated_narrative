# ruff: noqa: N806, F841, B023  (spike: nombres de imagen en mayúscula, como en la 790)
"""Spec-820 S1: componer primero, fotografiar una vez.

Por plantilla: la composición de S0 (tanda 9: la luz ya puesta) es la imagen de partida y los
bordes de la composición de la tanda 8 son la guía del ControlNet. Z-Image saca el cuadro entero
en una pasada (`foto_controlnet`). Dos modos: «respeta» (guía firme, poco cambio) y
«reinterpreta» (guía suelta, mucho cambio).

  set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 \
    uv run python scripts/research/820/s1_una_foto.py --plantillas A_der --modos respeta reinterpreta
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from src.infrastructure.adapters.comfy.client import ComfyClient

ID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
BASE = Path(f"data/dev/miniaturas/{ID}")
AQUI = Path(__file__).parent
MODOS = {
    "respeta": {"cambio": 0.62, "fuerza": 0.60},
    "reinterpreta": {"cambio": 0.80, "fuerza": 0.45},
}


def guia_de_bordes(im: Image.Image) -> Image.Image:
    """Bordes blancos sobre negro (como un scribble) de la composición."""
    g = ImageOps.grayscale(im).filter(ImageFilter.GaussianBlur(1.2))
    e = ImageOps.autocontrast(g.filter(ImageFilter.FIND_EDGES), cutoff=2)
    return e.point(lambda v: 255 if v > 90 else 0).filter(ImageFilter.MaxFilter(3)).convert("RGB")


def guia_profundidad(t: str) -> Image.Image:
    """Profundidad falsa: lo oscuro y cercano (figura, troncos de adelante) en blanco, la niebla
    lejana en negro. Sale de la composición con luz (S0) y del alfa de la figura."""
    s0 = ImageOps.grayscale(Image.open(BASE / "tanda_9" / f"{t}.jpg"))
    lejos = ImageOps.invert(s0.filter(ImageFilter.GaussianBlur(6)))
    alfa = (
        Image.open(BASE / "tanda_8" / f"{t}_alfa.png")
        .convert("L")
        .filter(ImageFilter.GaussianBlur(3))
    )
    cerca = Image.composite(Image.new("L", s0.size, 255), lejos, alfa)
    cerca = ImageOps.autocontrast(cerca, cutoff=1).point(lambda v: round(255 * (v / 255) ** 2.2))
    return cerca.convert("RGB")


def guia_gruesa(im: Image.Image) -> Image.Image:
    """Bordes de las formas grandes, sin la textura (la corteza)."""
    g = ImageOps.grayscale(im).filter(ImageFilter.GaussianBlur(5))
    e = ImageOps.autocontrast(g.filter(ImageFilter.FIND_EDGES), cutoff=1)
    return e.point(lambda v: 255 if v > 60 else 0).filter(ImageFilter.MaxFilter(5)).convert("RGB")


def prompt() -> str:
    datos = json.loads(Path(AQUI / "salidas" / "textos.json").read_text())
    return (AQUI / "prompts" / "una_foto.md").read_text().strip().format(**datos)


async def main(plantillas, modos, semilla, prompt_file, guias):
    out = AQUI / "salidas" / "s1"
    out.mkdir(parents=True, exist_ok=True)
    texto = prompt() if prompt_file is None else Path(prompt_file).read_text().strip()
    c = ComfyClient()
    registro = []
    for t in plantillas:
        inicio = BASE / "tanda_9" / f"{t}.jpg"
        comp = Image.open(BASE / "tanda_8" / f"{t}_sin_color.png")
        hechas = {
            "bordes": lambda: guia_de_bordes(comp),
            "gruesa": lambda: guia_gruesa(comp),
            "profundidad": lambda: guia_profundidad(t),
        }
        for tg in guias:
            guia = out / f"{t}_guia_{tg}.png"
            hechas[tg]().save(guia)
            for m in modos:
                p = MODOS[m]
                t0 = time.time()
                dest = out / f"{t}_{tg}_{m}_{semilla}.png"
                await c.correr(
                    "foto_controlnet",
                    {
                        "prompt": texto,
                        "semilla": semilla,
                        "cambio": p["cambio"],
                        "fuerza": p["fuerza"],
                        "prefijo": "spec820/s1",
                    },
                    {"imagen": inicio, "guia": guia},
                    dest,
                )
                registro.append(
                    {
                        "plantilla": t,
                        "guia": tg,
                        "modo": m,
                        "semilla": semilla,
                        **p,
                        "segundos": round(time.time() - t0, 1),
                        "archivo": dest.name,
                    }
                )
                print(registro[-1], flush=True)
    await c.liberar()
    (out / f"registro_{int(time.time())}.json").write_text(json.dumps(registro, indent=1))


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--plantillas", nargs="+", default=["A_der"])
    a.add_argument("--modos", nargs="+", default=list(MODOS))
    a.add_argument("--semilla", type=int, default=820)
    a.add_argument("--prompt-file")
    a.add_argument("--guias", nargs="+", default=["profundidad", "gruesa"])
    x = a.parse_args()
    asyncio.run(main(x.plantillas, x.modos, x.semilla, x.prompt_file, x.guias))
