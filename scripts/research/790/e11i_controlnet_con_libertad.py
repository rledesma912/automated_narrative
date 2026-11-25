"""Spike E11i: Qwen dibuja con trazo de historieta y Z-Image a 0,45 lo conserva (tanda 5); con
más libertad pierde la composición (E11f) y Qwen-Edit no sale del dibujo (E11h). ¿El ControlNet
Union de Z-Image con el boceto de Yael fijando la composición, y Z-Image con mucha libertad
(0,75 o desde cero), reinterpreta todo como foto y conserva el lugar? Texto: el de E11g (la IA
mira los bocetos y nombra con palabras de foto)."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy, grilla  # noqa: E402
from e1_personaje import grafo_zcn, grafo_zimage, scribble  # noqa: E402

RAIZ = AQUI.parents[2]
SID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
C = RAIZ / "data/dev/miniaturas" / SID
E11G = AQUI / "e11g/salidas"
SAL = AQUI / "e11i" / "salidas"
TXT = json.loads((E11G / "textos_foto.json").read_text())["escenario"]
PROMPT = (RAIZ / "config/miniatura/prompts/fotografiar_escenario.md").read_text().strip().replace("{descripcion}", TXT)
SEM = [990851, 11]



def img2img_cn(prompt, s, prefijo, imagen, denoise, control, fuerza):
    """Como E11d: Z-Image img2img con el ControlNet Union."""
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
        ctrl = await c.subir(ctrl_png)
        oscuros = {s: await c.subir(E11G / f"foto_s{s}/piezas/escenario_oscurecido.png") for s in SEM}
        variantes = {
            "cn75_f60": lambda s, p: img2img_cn(PROMPT, s, p, oscuros[s], 0.75, ctrl, 0.6),
            "cn75_f80": lambda s, p: img2img_cn(PROMPT, s, p, oscuros[s], 0.75, ctrl, 0.8),
            "cn100_f80": lambda s, p: grafo_zcn(PROMPT, s, p, ctrl, "full", 0.8),
        }
        for v, f in variantes.items():
            for s in SEM:
                d = SAL / f"{v}_s{s}.png"
                if d.exists():
                    continue
                r = await c.correr(f(s, f"spec790/e11i/{v}_{s}"))
                await c.bajar(r.imagenes[0], d)
                print(d.name, r.segundos, flush=True)
        await c.liberar()
    filas = [("hoy (E11g)", [(f"s{s}", E11G / f"foto_s{s}/piezas/escenario.png") for s in SEM])]
    filas += [(v, [(f"s{s}", SAL / f"{v}_s{s}.png") for s in SEM]) for v in variantes]
    print(grilla(filas, SAL / "grilla.png", ancho_celda=640))


if __name__ == "__main__":
    asyncio.run(main())
