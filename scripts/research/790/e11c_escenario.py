"""Spike E11c (Spec-790 T6.3): el escenario de Peter trae una mujer (Qwen: la descripción
nombra «el personaje») y una caseta (Z-Image: el prompt nombraba tejas, piedra, madera).
Compara los prompts de hoy con los nuevos de e11c/, con la misma cadena del arnés:
Qwen → curva → Z-Image 0,45.

    uv run python e11c_escenario.py [--semillas …]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy, grilla  # noqa: E402
from e1_personaje import grafo_qwen, grafo_zimage  # noqa: E402
from e3c_oscuro import curva  # noqa: E402

RAIZ = AQUI.parents[2]
PROMPTS = RAIZ / "config/miniatura/prompts"
SALIDAS = AQUI / "e11c" / "salidas"
SID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
BOCETO = RAIZ / "data/dev/miniaturas" / SID / "bocetos/escenario.png"
DESC = (
    "Un bosque denso, con muchos árboles secos y algunos frondosos, plantas, pastizales, y una "
    "niebla blanquecina espesa, que hace que el personaje resalte del fondo. Hiperrealista, debe "
    "parecer una foto real."
)
VARIANTES = {
    "hoy": (PROMPTS / "escenario.md", PROMPTS / "fotografiar_escenario.md"),
    "nuevo": (AQUI / "e11c/escenario_nuevo.md", AQUI / "e11c/fotografiar_nuevo.md"),
    # Z-Image (cfg 1) no tiene negativo: nombrar «casas» las trae. Solo en positivo, sobre el
    # mismo Qwen de «nuevo».
    "positivo": (AQUI / "e11c/escenario_nuevo.md", AQUI / "e11c/fotografiar_positivo.md"),
    "salvaje": (AQUI / "e11c/escenario_nuevo.md", AQUI / "e11c/fotografiar_salvaje.md"),
}
MISMO_QWEN = {"positivo": "nuevo", "salvaje": "nuevo"}


def texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8").strip().replace("{descripcion}", DESC)


async def main(semillas: list[int]) -> None:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    async with Comfy() as c:
        boceto = await c.subir(BOCETO)
        for v, (pq, _) in VARIANTES.items():
            if v in MISMO_QWEN:
                continue
            for s in semillas:
                d = SALIDAS / f"{v}_qwen_s{s}.png"
                if not d.exists():
                    r = await c.correr(grafo_qwen(boceto, texto(pq), s, f"spec790/e11c/{v}_q_{s}"))
                    await c.bajar(r.imagenes[0], d)
                    print(d.name, r.segundos, flush=True)
        await c.liberar()
        for v, (_, pz) in VARIANTES.items():
            for s in semillas:
                d = SALIDAS / f"{v}_foto_s{s}.png"
                if d.exists():
                    continue
                q = MISMO_QWEN.get(v, v)
                oscuro = curva(SALIDAS / f"{q}_qwen_s{s}.png", SALIDAS / f"{q}_oscuro_s{s}.png")
                sub = await c.subir(oscuro)
                r = await c.correr(grafo_zimage(texto(pz), s, f"spec790/e11c/{v}_z_{s}", sub, 0.45))
                await c.bajar(r.imagenes[0], d)
                print(d.name, r.segundos, flush=True)
        await c.liberar()


def grillas(semillas: list[int]) -> None:
    filas = []
    for v in VARIANTES:
        for paso in ("qwen", "foto"):
            if v in MISMO_QWEN and paso == "qwen":
                continue
            filas.append((f"{v} {paso}", [("boceto", BOCETO)] + [
                (f"s{s}", SALIDAS / f"{v}_{paso}_s{s}.png") for s in semillas]))
    print(grilla(filas, SALIDAS / "grilla.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    semilla_arnes = int(hashlib.sha256(SID.encode()).hexdigest()[:16], 16) % 1_000_000
    ap.add_argument("--semillas", default=f"{semilla_arnes},11,22")
    a = ap.parse_args()
    sem = [int(x) for x in a.semillas.split(",")]
    asyncio.run(main(sem))
    grillas(sem)
