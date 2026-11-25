"""Spike E3c (Spec-790 §10.0): Yael y el usuario aprobaron E3b (qwen_b → Z-Image img2img 0,45)
pero piden MENOS LUCES, lugares MÁS OSCUROS y CON NIEBLA.

De dónde viene la luz: la descripción (velas encendidas, luz alrededor de la cabina), la imagen
de Qwen (ya iluminada; Z-Image al 45 % respeta su brillo) y el prompt (pedía luna, no oscuridad).

Parte de las salidas `qwen_b` de E3 y prueba:
  oscuro_45        prompt de noche muy oscura + niebla espesa + «nada más que lo descrito»,
                   descripción sin «lit»; Z-Image img2img 0,45
  oscuro_55        ídem, denoise 0,55 (se aleja más del brillo de Qwen)
  previo_45        Python oscurece la imagen de Qwen ANTES (curva), y Z-Image 0,45 con el
                   prompt oscuro: parte de una escena oscura
  oscuro_45_curva  oscuro_45 + curva de oscuridad en Python DESPUÉS (sin GPU)

    uv run python e3c_oscuro.py [--variantes …] [--semillas 11,22,33]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, INSUMOS, Comfy, ComfyError, grilla  # noqa: E402
from e1_personaje import grafo_zimage  # noqa: E402

SALIDAS = AQUI / "e3c" / "salidas"
E3 = AQUI / "e3" / "salidas"
E3B = AQUI / "e3b" / "salidas"

OSCURO = (
    "A real, unedited photograph taken on a very dark night with a full-frame camera and a "
    "35mm lens, black and white, underexposed. Almost no light: only a faint, diffuse "
    "moonglow coming through thick fog. No lamps, no lit windows, no glowing lights, no "
    "candle flames, no bright moon. Dense fog fills the scene and swallows the distance; "
    "most of the image is in deep darkness, shapes barely visible. Realistic materials and "
    "textures: weathered wood, old stone, real roof tiles, real pine needles and bark, real "
    "grass and dirt. Natural film grain. It must look like a real place photographed by a "
    "person: not an illustration, not a drawing, not a cartoon, not a 3D render, not CGI, "
    "not stylized. Nobody in the scene: no people, no creatures, no animals. Nothing else "
    "besides what is described: no extra objects."
)

# Las mismas escenas de E3, sin luces encendidas.
BOCETOS = {
    "torre": "A dense pine forest at night seen from just above the treetops, a tall "
    "wooden fire lookout tower on four long legs rising among the trees on the right, its "
    "small dark cabin with a pointed roof, a narrow balcony and dark windows, mountains far "
    "behind, lost in the fog.",
    "mansion": "A large old abandoned Victorian mansion seen from the front: pointed "
    "towers, tiled roofs and chimneys, balconies with iron railings, rows of dark arched "
    "windows, a dark front door at the top of wide stone stairs, two unlit candles and two "
    "carved jack-o'-lanterns at the foot of the stairs, a winding dirt path leading to the "
    "stairs, big bare trees on the left and a row of tall poplar trees on the right.",
}
ARCHIVOS = {"torre": "torre_escenario.png", "mansion": "mansion_escenario.png"}


def curva(origen: Path, destino: Path, gamma: float = 1.6, techo: float = 0.75) -> Path:
    """Oscurece sin IA: medios tonos hacia abajo (gamma) y luces altas recortadas (techo).
    Lo negro sigue negro; una luz fuerte queda gris."""
    from PIL import Image

    lut = [round(255 * techo * (v / 255) ** gamma) for v in range(256)]
    im = Image.open(origen).convert("RGB")
    im.point(lut * 3).save(destino)
    return destino


VARIANTES = ["oscuro_45", "oscuro_55", "previo_45"]


async def main(variantes: list[str], semillas: list[int]) -> dict:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    medidas_ruta = SALIDAS / "medidas.json"
    medidas = json.loads(medidas_ruta.read_text()) if medidas_ruta.exists() else {}
    async with Comfy() as c:
        entrada = {}
        for k in BOCETOS:
            for s in semillas:
                qwen = E3 / f"{k}_qwen_b_s{s}.png"
                entrada[(k, s, "qwen")] = await c.subir(qwen)
                previa = curva(qwen, SALIDAS / f"{k}_qwen_b_oscurecida_s{s}.png")
                entrada[(k, s, "previa")] = await c.subir(previa)
        await c.liberar()
        for v in variantes:
            denoise = 0.55 if v == "oscuro_55" else 0.45
            fuente = "previa" if v == "previo_45" else "qwen"
            for k, desc in BOCETOS.items():
                for s in semillas:
                    clave = f"{k}_{v}_s{s}"
                    grafo = grafo_zimage(
                        f"{OSCURO} {desc}",
                        s,
                        f"spec790/e3c/{clave}",
                        entrada[(k, s, fuente)],
                        denoise,
                    )
                    try:
                        r = await c.correr(grafo)
                    except ComfyError as e:
                        medidas[clave] = {"error": str(e), "detalle": e.detalle[:500]}
                        print(clave, "ERROR", e, e.detalle[:200], flush=True)
                        continue
                    destino = SALIDAS / f"{clave}.png"
                    await c.bajar(r.imagenes[0], destino)
                    if v == "oscuro_45":
                        curva(destino, SALIDAS / f"{k}_oscuro_45_curva_s{s}.png", 1.35, 0.85)
                    medidas[clave] = {"segundos": r.segundos, "vram_pico_mb": r.vram_pico_mb}
                    print(clave, medidas[clave], flush=True)
                    medidas_ruta.write_text(json.dumps(medidas, indent=2))
        await c.liberar()
    return medidas


def grillas(semillas: list[int]) -> None:
    for k in BOCETOS:
        boceto = INSUMOS / "bocetos" / ARCHIVOS[k]
        filas = [
            (
                "zimg_45 (E3b)",
                [("boceto", boceto)] + [(f"s{s}", E3B / f"{k}_zimg_45_s{s}.png") for s in semillas],
            )
        ]
        for v in VARIANTES + ["oscuro_45_curva"]:
            celdas = [("boceto", boceto)] + [
                (f"s{s}", SALIDAS / f"{k}_{v}_s{s}.png")
                for s in semillas
                if (SALIDAS / f"{k}_{v}_s{s}.png").exists()
            ]
            if len(celdas) > 1:
                filas.append((v, celdas))
        print(grilla(filas, SALIDAS / f"grilla_{k}.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variantes", default=",".join(VARIANTES))
    ap.add_argument("--semillas", default="11,22,33")
    ap.add_argument("--solo-grilla", action="store_true")
    a = ap.parse_args()
    sem = [int(x) for x in a.semillas.split(",")]
    if not a.solo_grilla:
        asyncio.run(main(a.variantes.split(","), sem))
    grillas(sem)
