"""Spike E11h: Qwen copia el trazo del boceto (hojas planas) y Z-Image a 0,45 no lo cambia.
¿Un paso de Qwen-Edit sobre su propia imagen («volvé foto esta ilustración, cada planta dibujada
es una planta real») antes de la curva y de Z-Image saca el dibujo y conserva la atmósfera?"""

import asyncio
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comun import grilla  # noqa: E402
from PIL import Image  # noqa: E402

from src.application.services.miniatura import imagen as im_  # noqa: E402
from src.application.services.miniatura.arte import arte, prompt  # noqa: E402
from src.infrastructure.adapters.comfy.client import ComfyClient  # noqa: E402

AQUI = Path(__file__).resolve().parent
SID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
C = RAIZ / "data/dev/miniaturas" / SID
E11G = AQUI / "e11g/salidas"
SAL = AQUI / "e11h/salidas"
REINT = (AQUI / "e11h/reinterpretar.md").read_text().strip()
SEM_PROD = 0  # se completa abajo


async def una(c: ComfyClient, nombre: str, crudo: Path, desc: str, s: int) -> tuple[Path, Path]:
    d = SAL / nombre
    d.mkdir(parents=True, exist_ok=True)
    real = d / "reinterpretado.png"
    if not real.exists():
        await c.correr("boceto_a_imagen", {"prompt": REINT.replace("{descripcion}", desc), "semilla": s}, {"boceto": crudo}, real)
    foto = d / "foto.png"
    if not foto.exists():
        osc = d / "oscuro.png"
        im_.oscurecer_escenario(Image.open(real), arte()).save(osc)
        await c.correr("foto_img2img", {"prompt": prompt("fotografiar_escenario", desc), "semilla": s, "cambio": arte().escenario.cambio_foto}, {"imagen": osc}, foto)
    print(nombre, flush=True)
    return real, foto


async def main():
    from src.application.services.miniatura.arnes import _hash

    sp = int(_hash(SID), 16) % 1_000_000
    t5 = json.loads((RAIZ / "scripts/research/790/e11f/salidas/textos.json").read_text())["escenario"]
    tg = json.loads((E11G / "textos_foto.json").read_text())["escenario"]
    c = ComfyClient()
    filas = []
    casos = [
        ("tanda5", C / "piezas/escenario_crudo.png", C / "piezas/escenario.png", t5, sp),
        ("e11g_s" + str(sp), E11G / f"foto_s{sp}/piezas/escenario_crudo.png", E11G / f"foto_s{sp}/piezas/escenario.png", tg, sp),
        ("e11g_s11", E11G / "foto_s11/piezas/escenario_crudo.png", E11G / "foto_s11/piezas/escenario.png", tg, 11),
    ]
    for nombre, crudo, foto_antes, desc, s in casos:
        real, foto = await una(c, nombre, crudo, desc, s)
        filas.append((nombre, [("qwen", crudo), ("foto sin paso", foto_antes), ("reinterpretado", real), ("foto con paso", foto)]))
    await c.liberar()
    print(grilla(filas, SAL / "grilla.png", ancho_celda=480))


asyncio.run(main())
