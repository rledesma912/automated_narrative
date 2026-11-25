"""Spike E9 (Spec-790 §10.0): la cadena completa por Python, para una historia (la coneja).

boceto personaje → Qwen (color) → BiRefNet → recorte; boceto escenario → Qwen → curva → Z-Image
0,45; compositor (4 plantillas, sin título) + fundido; tono del lugar (C5c). Mide el tiempo de
cada paso y el total, y la VRAM pico de toda la placa (nvidia-smi en paralelo).

    uv run python e9_cadena.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c3_compositor as c3  # noqa: E402
import c5_color as c5  # noqa: E402
import c5c_tono_lugar as c5c  # noqa: E402
from comun import AQUI  # noqa: E402

SALIDAS = AQUI / "e9" / "salidas"


async def main() -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    c5.SALIDAS = SALIDAS
    c5.CASOS = {"coneja": c5.CASOS["coneja"]}
    c3.CASOS = {"coneja": c3.CASOS["coneja"]}
    vram = subprocess.Popen(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits", "-lms", "500"],
        stdout=open(SALIDAS / "vram.txt", "w"),
    )
    t0 = time.time()
    medidas = await c5.piezas([22])
    t_piezas = time.time() - t0
    t1 = time.time()
    await c5.componer(22)
    t_comp = time.time() - t1
    t2 = time.time()
    for pn in c3.PLANTILLAS:
        im = Image.open(SALIDAS / "comp" / f"coneja_{pn}.png").convert("RGB")
        c5c.entonar(im, "gris_frio").save(SALIDAS / f"coneja_{pn}_final.png")
    t_tono = time.time() - t2
    vram.terminate()
    valores = [int(x) for x in (SALIDAS / "vram.txt").read_text().split() if x.isdigit()]
    out = {
        "piezas_s": round(t_piezas, 1), "componer_y_fundir_s": round(t_comp, 1),
        "tono_s": round(t_tono, 1), "total_s": round(time.time() - t0, 1),
        "vram_pico_mb": max(valores) if valores else None, "pasos": medidas,
    }
    (SALIDAS / "medidas.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    asyncio.run(main())
