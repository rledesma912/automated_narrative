"""Spike E11d: el paso a foto del escenario (Z-Image) no ve el boceto y convierte una planta en
una persona sentada (tanda 4 de Peter). ¿Menos libertad (0,30 / 0,35) o el boceto como guía
(ControlNet Union de Z-Image con el scribble de Yael)? Sobre el mismo escenario oscurecido de
la tanda 4 y con el texto que escribió la IA (T3.3)."""

import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy, grilla  # noqa: E402
from e1_personaje import grafo_zcn, grafo_zimage, scribble  # noqa: E402

RAIZ = AQUI.parents[2]
SID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
C = RAIZ / "data/dev/miniaturas" / SID
SAL = AQUI / "e11d" / "salidas"
TXT = json.load(urllib.request.urlopen(f"http://localhost:8040/api/v1/stories/{SID}/thumbnail"))["texts"]
PROMPT = (RAIZ / "config/miniatura/prompts/fotografiar_escenario.md").read_text().strip().replace(
    "{descripcion}", TXT["escenario"]
)
SEM = [990851, 11]


def img2img_cn(prompt, s, prefijo, imagen, denoise, control, fuerza):
    g = grafo_zcn(prompt, s, prefijo, control, "full", fuerza)
    base = grafo_zimage(prompt, s, prefijo, imagen, denoise)
    for k in ("9", "10", "11"):
        g[k] = base[k]
    g["6"]["inputs"]["latent_image"] = ["11", 0]
    g["6"]["inputs"]["denoise"] = denoise
    return g


async def main():
    SAL.mkdir(parents=True, exist_ok=True)
    ctrl_png = scribble(C / "bocetos/escenario.png", SAL / "scribble.png")
    async with Comfy() as c:
        oscuro = await c.subir(C / "piezas/escenario_oscurecido.png")
        ctrl = await c.subir(ctrl_png)
        variantes = {
            "z45": lambda s, p: grafo_zimage(PROMPT, s, p, oscuro, 0.45),
            "z35": lambda s, p: grafo_zimage(PROMPT, s, p, oscuro, 0.35),
            "z30": lambda s, p: grafo_zimage(PROMPT, s, p, oscuro, 0.30),
            "cn45_50": lambda s, p: img2img_cn(PROMPT, s, p, oscuro, 0.45, ctrl, 0.5),
            "cn45_70": lambda s, p: img2img_cn(PROMPT, s, p, oscuro, 0.45, ctrl, 0.7),
        }
        for v, f in variantes.items():
            for s in SEM:
                d = SAL / f"{v}_s{s}.png"
                if d.exists():
                    continue
                r = await c.correr(f(s, f"spec790/e11d/{v}_{s}"))
                await c.bajar(r.imagenes[0], d)
                print(d.name, r.segundos, flush=True)
        await c.liberar()
    filas = [(v, [("qwen", C / "piezas/escenario_crudo.png")] + [(f"s{s}", SAL / f"{v}_s{s}.png") for s in SEM])
             for v in variantes]
    print(grilla(filas, SAL / "grilla.png", ancho_celda=480))


asyncio.run(main())
