"""Spike E12: «semi escondido detrás de un árbol». Python solo puede oscurecer; ¿el fundido de
Qwen-Edit (el mismo paso, el mismo recorte) con la relación en el prompt pone el tronco por
delante del cuerpo? Sobre los recortes de la tanda 5 de Peter."""

import asyncio
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comun import grilla  # noqa: E402

from src.application.services.miniatura.arte import prompt  # noqa: E402
from src.infrastructure.adapters.comfy.client import ComfyClient  # noqa: E402

AQUI = Path(__file__).resolve().parent
C = RAIZ / "data/dev/miniaturas/598a3b1d-75ff-4e6b-bae4-4db465468fbf/tanda_5"
SAL = AQUI / "e12/salidas"
DETRAS = (AQUI / "e12/fundir_detras.md").read_text().strip()
SEM = [7, 99]


async def main():
    SAL.mkdir(parents=True, exist_ok=True)
    c = ComfyClient()
    filas = []
    for clave in ("A_der", "A_izq"):
        zona = C / f"{clave}_zona.png"
        celdas = [("recorte", zona), ("hoy", C / f"{clave}_fundido.png")]
        for s in SEM:
            d = SAL / f"{clave}_detras_s{s}.png"
            if not d.exists():
                await c.correr("boceto_a_imagen", {"prompt": DETRAS, "semilla": s}, {"boceto": zona}, d)
                print(d.name, flush=True)
            celdas.append((f"detrás s{s}", d))
        filas.append((clave, celdas))
    await c.liberar()
    assert prompt("fundir")
    print(grilla(filas, SAL / "grilla.png", ancho_celda=400))


asyncio.run(main())
