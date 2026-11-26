"""Spike H1a, segunda vuelta (Spec-800): los ojos como dice Yael (cuencas negras con un brillo
violeta chico adentro, la boca oscura) y tres ideas de ropa de «anfitrión de cripta» sobre la
misma imagen, cambiando solo la ropa (Qwen-Edit, una tarea por llamada: primero los ojos,
después la ropa).

    set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 \\
    uv run python scripts/research/800/h1a2_ojos_y_ropa.py ojos
    uv run python scripts/research/800/h1a2_ojos_y_ropa.py ropa <ojos_elegido.png>
"""

import asyncio
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from src.infrastructure.adapters.comfy.client import ComfyClient  # noqa: E402

AQUI = Path(__file__).resolve().parent
SAL = AQUI / "h1a3/salidas"  # segunda base: la cabeza de Yael
BASE = AQUI / "h1a/salidas/avatar_sola_s11.png"  # la cabeza que eligió Yael (2026-11-26)
PROMPTS = RAIZ / "config/personajes/prompts"

ROPAS = {
    "anfitrion": (
        "He is tall and thin with long limbs, slightly hunched forward like someone about to "
        "tell a secret. He wears a long worn black velvet frock coat with a deep violet lining, "
        "frayed at the cuffs and the hem, a dark waistcoat with tarnished brass buttons and a "
        "pocket watch chain, an old high-collared shirt with a frayed black cravat, worn dark "
        "formal trousers and old black lace-up ankle boots. Dry pumpkin vine tendrils and a "
        "few withered leaves curl out of his collar and his cuffs. Dust and a few cobwebs on "
        "his shoulders."
    ),
    "sepulturero": (
        "He is tall and thin with long limbs, slightly hunched. He wears a long ragged black "
        "hooded cloak with the hood down on his back, over a dark waistcoat with tarnished "
        "brass buttons, an old collarless shirt, worn dark trousers tucked into tall old black "
        "leather boots, and a gravedigger's worn leather belt. Dust and cobwebs on the cloak."
    ),
    "planta": (
        "His body is tall, very thin and made of twisted dry pumpkin vines and roots, visible "
        "at the neck, the wrists and the ankles, with a few withered leaves and curling "
        "tendrils. He wears a long worn black frock coat with a deep violet lining, frayed at "
        "the hem, and a dark waistcoat with tarnished brass buttons. His feet are tangled "
        "gnarled roots instead of shoes."
    ),
}


async def ojos():
    SAL.mkdir(parents=True, exist_ok=True)
    c = ComfyClient()
    p = (PROMPTS / "ojos.md").read_text().strip()
    for s in (5, 55, 555):
        d = SAL / f"ojos_s{s}.png"
        if not d.exists():
            await c.correr("boceto_a_imagen", {"prompt": p, "semilla": s}, {"boceto": BASE}, d)
            print(d.name, flush=True)
    await c.liberar()


async def ropa(base: Path):
    c = ComfyClient()
    plantilla = (PROMPTS / "ropa.md").read_text().strip()
    for clave, texto in ROPAS.items():
        for s in (7, 77):
            d = SAL / f"ropa_{clave}_s{s}.png"
            if not d.exists():
                await c.correr(
                    "boceto_a_imagen",
                    {"prompt": plantilla.format(ropa=texto), "semilla": s},
                    {"boceto": base},
                    d,
                )
                print(d.name, flush=True)
    await c.liberar()


if sys.argv[1] == "ojos":
    asyncio.run(ojos())
else:
    asyncio.run(ropa(Path(sys.argv[2])))
