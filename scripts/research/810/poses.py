"""Spec-810 §1b punto 2: poses de inicio para los tramos (Qwen-Edit, una por llamada) y los ojos
de Yael arreglados en Python sobre cada una (cuenca negra, pupila violeta tenue).

    set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 uv run python scripts/research/810/poses.py
"""

import asyncio
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arnes as A  # noqa: E402

from src.infrastructure.adapters.comfy.client import ComfyClient  # noqa: E402

AQUI = Path(__file__).resolve().parent
SAL = AQUI / "poses/salidas"
BASE = A.RAIZ / "scripts/research/800/h1a3/salidas/ojos_py_70_200.png"
PROMPT = (A.RAIZ / "config/personajes/prompts/pose.md").read_text().strip()
POSES = {
    "mano": "he raises his free left hand in an open, expressive welcoming gesture, palm up, like a host greeting his guests.",
    "inclinado": "he leans his upper body forward toward the camera, as if telling a secret, the microphone close to his carved mouth.",
    "atras": "he leans back a little with his shoulders relaxed and his free hand open to the side, amused, like someone laughing at a dark joke.",
    "ladeado": "he tilts his head to one side and turns his shoulders slightly, mischievous, with his free hand pointing at the viewer.",
}


async def main(semillas: list[int]) -> None:
    SAL.mkdir(parents=True, exist_ok=True)
    c = ComfyClient()
    for clave, pose in POSES.items():
        for s in semillas:
            d = SAL / f"{clave}_s{s}_crudo.png"
            if not d.exists():
                await c.correr(
                    "boceto_a_imagen",
                    {"prompt": PROMPT.format(pose=pose), "semilla": s},
                    {"boceto": BASE},
                    d,
                )
            A.oscurecer_ojos(Image.open(d).convert("RGB")).save(SAL / f"{clave}_s{s}.png")
            print(d.name, flush=True)
    await c.liberar()


asyncio.run(main([int(x) for x in sys.argv[1:]] or [7]))
