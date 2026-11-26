"""Spec-810: el fondo de cripta para las imágenes de inicio (Qwen-Edit, una llamada por imagen).
Después vuelve a pegar la cabeza de la imagen de entrada (como la Spec-800 H1a) y arregla los ojos.

    uv run python scripts/research/810/fondo.py <imagen.png> [...]   → <imagen>_cripta.png
"""

import asyncio
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "800"))
import arnes as A  # noqa: E402
import h1a3_cabeza as C  # noqa: E402

from src.infrastructure.adapters.comfy.client import ComfyClient  # noqa: E402

PROMPT = (A.RAIZ / "config/personajes/prompts/fondo_cripta.md").read_text().strip()


async def main(rutas: list[Path], semilla: int = 5) -> None:
    c = ComfyClient()
    for r in rutas:
        crudo = r.with_name(r.stem + "_cripta_crudo.png")
        if not crudo.exists():
            await c.correr(
                "boceto_a_imagen", {"prompt": PROMPT, "semilla": semilla}, {"boceto": r}, crudo
            )
        cab = Image.open(r).convert("RGB")
        C.ARRIBA = int(cab.height * 0.5)
        final = C.proteger(cab, Image.open(crudo))
        A.oscurecer_ojos(final).save(r.with_name(r.stem + "_cripta.png"))
        print(r.with_name(r.stem + "_cripta.png").name, flush=True)
    await c.liberar()


asyncio.run(main([Path(a) for a in sys.argv[1:]]))
