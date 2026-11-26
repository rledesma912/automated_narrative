"""Spike V2 (Spec-810): la calabaza habla con LTX-2.3, con el mismo arnés, las mismas poses y el
mismo audio que V1, para comparar.

    set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 \\
    uv run python scripts/research/810/v2_ltx.py --poses <p1.png> ... --planos medio cerrado ...
"""

import argparse
import asyncio
import math
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arnes as A  # noqa: E402
import v1_infinitetalk as V1  # noqa: E402

AQUI = Path(__file__).resolve().parent
FPS_LTX = 24


def cuadros_ltx(segundos: float) -> int:
    """LTX pide 8k + 1 cuadros."""
    return 8 * math.ceil(segundos * FPS_LTX / 8) + 1


async def correr(
    formato: str,
    prompt: str,
    voz: str,
    max_s: float,
    poses: list[Path],
    planos: list[str] | None,
    semilla: int,
    solo_uno: bool,
) -> Path:
    ancho, alto, rel = V1.FORMATOS[formato]
    sal = AQUI / f"v2/salidas/{formato}_{prompt}_{voz}"
    sal.mkdir(parents=True, exist_ok=True)
    inicios = []
    for k, p in enumerate(poses):
        im = A.encuadrar(Image.open(p).convert("RGB"), ancho, alto, rel)
        im.save(sal / f"inicio_{k}.png")
        inicios.append(im)
    audio = A.a_wav16(V1.AUDIOS / f"prueba_{voz}.wav", sal / "audio.wav")
    cortes = A.tramos(A.muestras(audio), max_s)[: 1 if solo_uno else None]
    c = A.ClienteVideo()
    await c.liberar()
    corrida = {
        "modelo": "ltx-2.3",
        "formato": formato,
        "prompt": prompt,
        "voz": voz,
        "max_s": max_s,
        "tramos": [],
        "inicio": time.strftime("%Y-%m-%d %H:%M"),
    }
    clips = []
    for i, (desde, hasta) in enumerate(cortes):
        k = i % len(inicios)
        tramo = A.recortar_audio(audio, desde, hasta, sal / f"tramo_{i}.wav")
        n = cuadros_ltx(hasta - desde)
        destino = sal / f"tramo_{i}_s{semilla}.mp4"
        med = {"segundos": None, "vram_pico_mb": None}
        if not destino.exists():
            med = await c.clip(
                "ltx",
                {
                    "prompt": V1.PROMPTS[prompt],
                    "segundos": round(hasta - desde, 3),
                    "ancho_1": ancho // 2,
                    "alto_1": alto // 2,
                    "cuadros": n,
                    "semilla": semilla,
                    "prefijo": f"spec810/v2_{formato}_{i}",
                },
                {"imagen": sal / f"inicio_{k}.png", "audio": tramo},
                destino,
            )
        ch = A.chequear(destino, inicios[k], tramo, sal / f"_cuadros_{i}")
        import shutil

        shutil.rmtree(sal / f"_cuadros_{i}", ignore_errors=True)
        print(f"tramo {i} ({hasta - desde:.1f} s, {n} cuadros): {med} → {ch}", flush=True)
        clips.append(destino)
        corrida["tramos"].append(
            {
                "desde": round(desde, 2),
                "hasta": round(hasta, 2),
                "cuadros": n,
                "pose": k,
                "semilla": semilla,
                **med,
                "chequeo": ch,
            }
        )
        A.guardar(corrida, sal)
    await c.liberar()
    destino = sal / f"calabaza_{formato}_{prompt}.mp4"
    final = (
        A.dirigir(clips, audio, destino, ancho, alto, planos)
        if planos
        else A.armar(clips, audio, destino, ancho, alto, True)
    )
    corrida["fin"] = time.strftime("%Y-%m-%d %H:%M")
    A.guardar(corrida, sal)
    print(final)
    return final


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--formato", default="h", choices=V1.FORMATOS)
    ap.add_argument("--prompt", default="vivo", choices=V1.PROMPTS)
    ap.add_argument("--voz", default="eric")
    ap.add_argument("--max-s", type=float, default=4.0)
    ap.add_argument("--poses", nargs="+", type=Path, required=True)
    ap.add_argument("--planos", nargs="*")
    ap.add_argument("--semilla", type=int, default=11)
    ap.add_argument("--solo-uno", action="store_true")
    a = ap.parse_args()
    asyncio.run(
        correr(a.formato, a.prompt, a.voz, a.max_s, a.poses, a.planos, a.semilla, a.solo_uno)
    )
