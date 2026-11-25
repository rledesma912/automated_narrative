"""Spike E11f: la tanda 5 salió «de dibujo» (las hojas del boceto quedan como siluetas planas).
Con la descripción de la IA que mira los bocetos, ¿Z-Image puede tener más libertad (0,55–0,75)
sin volver a inventar la persona?"""

import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy, grilla  # noqa: E402
from e1_personaje import grafo_zimage  # noqa: E402

RAIZ = AQUI.parents[2]
SID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
C = RAIZ / "data/dev/miniaturas" / SID
P = RAIZ / "config/miniatura/prompts"
SAL = AQUI / "e11f" / "salidas"
SEM = [990851, 11]
CAMBIOS = [0.45, 0.55, 0.65, 0.75]


async def main():
    SAL.mkdir(parents=True, exist_ok=True)
    t = json.load(urllib.request.urlopen(f"http://localhost:8040/api/v1/stories/{SID}/thumbnail"))["texts"]
    (SAL / "textos.json").write_text(json.dumps(t, ensure_ascii=False, indent=1))
    foto_p = (P / "fotografiar_escenario.md").read_text().strip().replace("{descripcion}", t["escenario"])
    async with Comfy() as c:
        osc = await c.subir(C / "piezas/escenario_oscurecido.png")
        for s in SEM:
            for k in CAMBIOS:
                d = SAL / f"foto_{int(k * 100)}_s{s}.png"
                if not d.exists():
                    r = await c.correr(grafo_zimage(foto_p, s, f"spec790/e11f/z_{k}_{s}", osc, k))
                    await c.bajar(r.imagenes[0], d)
                    print(d.name, flush=True)
        await c.liberar()
    filas = [("tanda 5", [("qwen", C / "piezas/escenario_crudo.png"), ("foto 0,45", C / "piezas/escenario.png")])]
    for s in SEM:
        filas.append((f"s{s}", [(f"{k}", SAL / f"foto_{int(k * 100)}_s{s}.png") for k in CAMBIOS]))
    print(grilla(filas, SAL / "grilla.png", ancho_celda=480))


asyncio.run(main())
