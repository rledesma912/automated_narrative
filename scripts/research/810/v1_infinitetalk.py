"""Spike V1 (Spec-810): la calabaza habla con InfiniteTalk, a través del arnés.

    set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 \\
    uv run python scripts/research/800/../810/v1_infinitetalk.py --formato h --prompt tranquilo [--max-s 4] [--solo-uno] [--publicar]

Cada corrida deja en `810/v1/salidas/<formato>_<prompt>/`: el cuadro de inicio, los tramos de
audio, un clip por tramo (con sus reintentos), el video armado y `corrida.json`.
"""

import argparse
import asyncio
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arnes as A  # noqa: E402

from src.application.services.tablero.entregas import publicar  # noqa: E402

AQUI = Path(__file__).resolve().parent
BASE = A.RAIZ / "scripts/research/800/h1a3/salidas/ojos_py_70_200.png"  # la cabeza de Yael
AUDIOS = AQUI / "audio"
FORMATOS = {
    "h": (832, 480, 0.42),
    "v": (480, 832, 0.30),
}  # ancho, alto, cuánto del alto ocupa la cabeza
PROMPTS = {
    "vivo": (
        "A character whose head is a carved orange pumpkin with black headphones talks to the "
        "viewer in his dark stone crypt, holding a black studio microphone in his gloved hand. He "
        "nods and tilts his head as he speaks, moves the microphone a little closer and away, and "
        "gestures with his free hand. His carved mouth opens and closes with the words. Candle "
        "flames flicker, thin fog drifts near the floor. Expressive, theatrical, like a horror host "
        "telling a story. Cinematic."
    ),
    "tranquilo": (
        "A character whose head is a carved orange pumpkin with black headphones talks calmly into "
        "a black studio microphone held in his gloved hand. His carved mouth opens and closes with "
        "the words. Small natural head movements, the soft violet glow deep in his dark eye "
        "sockets flickers. Dark moody studio, cinematic, steady camera."
    ),
    "secreto": (
        "A character whose head is a carved orange pumpkin with black headphones leans slowly "
        "toward the camera as if telling a secret, speaking into a black studio microphone held in "
        "his gloved hand. His carved mouth opens and closes with the words. The soft violet glow "
        "deep in his dark eye sockets flickers. Dark moody studio, cinematic."
    ),
}
SEMILLAS = [11, 222, 3333]
REINTENTOS = 2


async def correr(
    formato: str,
    prompt: str,
    voz: str,
    max_s: float,
    solo_uno: bool,
    poses: list[Path] | None = None,
    reintentos: int = REINTENTOS,
    etiqueta: str = "",
    planos: list[str] | None = None,
) -> Path:
    ancho, alto, rel = FORMATOS[formato]
    sal = AQUI / f"v1/salidas/{formato}_{prompt}_{voz}{etiqueta}"
    sal.mkdir(parents=True, exist_ok=True)
    poses = poses or [BASE]
    inicios = []
    for k, p in enumerate(poses):
        im = A.encuadrar(Image.open(p).convert("RGB"), ancho, alto, rel)
        im.save(sal / f"inicio_{k}.png")
        inicios.append(im)
    inicio = inicios[0]
    inicio.save(sal / "inicio.png")
    audio = A.a_wav16(AUDIOS / f"prueba_{voz}.wav", sal / "audio.wav")
    cortes = A.tramos(A.muestras(audio), max_s)
    if solo_uno:
        cortes = cortes[:1]
    c = A.ClienteVideo()
    await c.liberar()
    corrida = {
        "modelo": "infinitetalk",
        "formato": formato,
        "prompt": prompt,
        "voz": voz,
        "max_s": max_s,
        "tramos": [],
        "inicio": time.strftime("%Y-%m-%d %H:%M"),
    }
    clips = []
    for i, (desde, hasta) in enumerate(cortes):
        tramo_wav = A.recortar_audio(audio, desde, hasta, sal / f"tramo_{i}.wav")
        n = A.cuadros_para(hasta - desde)
        intentos = []
        k_pose = i % len(inicios)
        inicio = inicios[k_pose]
        for semilla in SEMILLAS[: reintentos + 1]:
            destino = sal / f"tramo_{i}_s{semilla}.mp4"
            if not destino.exists():
                med = await c.clip(
                    "infinitetalk",
                    {
                        "prompt": PROMPTS[prompt],
                        "ancho": ancho,
                        "alto": alto,
                        "cuadros": n,
                        "semilla": semilla,
                        "pasos": 6,
                        "prefijo": f"spec810/v1_{formato}_{i}",
                    },
                    {"imagen": sal / f"inicio_{k_pose}.png", "audio": tramo_wav},
                    destino,
                )
            else:
                med = {"segundos": None, "vram_pico_mb": None}
            ch = A.chequear(destino, inicio, tramo_wav, sal / f"_cuadros_{i}_{semilla}")
            shutil.rmtree(sal / f"_cuadros_{i}_{semilla}", ignore_errors=True)
            intentos.append({"semilla": semilla, **med, "chequeo": ch})
            print(
                f"tramo {i} ({hasta - desde:.1f} s, {n} cuadros) s{semilla}: {med} → "
                f"{'pasa' if ch.pasa else ', '.join(ch.motivos)} {ch}",
                flush=True,
            )
            if ch.pasa:
                break
        elegido = next((x for x in intentos if x["chequeo"].pasa), intentos[0])
        clips.append(sal / f"tramo_{i}_s{elegido['semilla']}.mp4")
        corrida["tramos"].append(
            {
                "desde": round(desde, 2),
                "hasta": round(hasta, 2),
                "cuadros": n,
                "intentos": intentos,
                "elegido": elegido["semilla"],
            }
        )
        A.guardar(corrida, sal)
    await c.liberar()
    if planos:
        final = A.dirigir(
            clips, audio, sal / f"calabaza_{formato}_{prompt}.mp4", ancho, alto, planos
        )
    else:
        final = A.armar(
            clips, audio, sal / f"calabaza_{formato}_{prompt}.mp4", ancho, alto, cortes=True
        )
    corrida["fin"] = time.strftime("%Y-%m-%d %H:%M")
    A.guardar(corrida, sal)
    print(final)
    return final


def publicar_entrega(carpetas: list[Path], titulo: str, que_mirar: str, prod: bool) -> str:
    slug = f"{date.today()}-calabaza-habla-v1"
    entrega = AQUI / "v1" / slug
    shutil.rmtree(entrega, ignore_errors=True)
    entrega.mkdir(parents=True)
    imgs = []
    for s in carpetas:
        for v in s.glob("calabaza_*.mp4"):
            nombre = f"{s.name}_{v.name}"
            shutil.copy(v, entrega / nombre)
            imgs.append({"archivo": nombre, "leyenda": s.name.replace("_", " · ")})
    datos = {
        "titulo": titulo,
        "proyecto": "calabaza",
        "que_mirar": que_mirar,
        "filas": [{"titulo": "Los videos", "imagenes": imgs}],
    }
    (entrega / "entrega.yaml").write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False)
    )
    e = publicar(
        entrega, A.RAIZ / ("data/prod/tablero" if prod else "data/dev/tablero"), reemplazar=True
    )
    return f"/tablero/{e.id}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--formato", default="h", choices=FORMATOS)
    ap.add_argument("--prompt", default="tranquilo", choices=PROMPTS)
    ap.add_argument("--voz", default="eric")
    ap.add_argument("--max-s", type=float, default=4.0)
    ap.add_argument("--solo-uno", action="store_true")
    ap.add_argument(
        "--poses",
        nargs="*",
        type=Path,
        help="una imagen de inicio por tramo (en orden, se repiten)",
    )
    ap.add_argument("--reintentos", type=int, default=REINTENTOS)
    ap.add_argument("--etiqueta", default="")
    ap.add_argument(
        "--planos",
        nargs="*",
        help="dirección de cámara: un plano por tramo (medio, cerrado, lateral, ojos)",
    )
    a = ap.parse_args()
    asyncio.run(
        correr(
            a.formato,
            a.prompt,
            a.voz,
            a.max_s,
            a.solo_uno,
            a.poses,
            a.reintentos,
            a.etiqueta,
            a.planos,
        )
    )
