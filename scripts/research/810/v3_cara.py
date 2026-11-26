"""Spike V3 (Spec-810): la cara en primer plano y pegada. Para cada tramo:

1. Python recorta la cabeza de la pose de inicio en un cuadro de 512 × 512 (la boca, 3–4 veces
   más grande que en el plano medio).
2. LTX hace hablar ese primer plano con el audio del tramo (una llamada).
3. Python sigue la cabeza cuadro a cuadro en el clip del cuerpo (el de V2), escala y ubica la
   cabeza del primer plano encima y la pega con el borde suave.
4. La dirección de cámara de siempre.

  set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 uv run python scripts/research/810/v3_cara.py
"""

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arnes as A  # noqa: E402
import v2_ltx as V2  # noqa: E402

from src.application.services.miniatura.imagen import igualar  # noqa: E402

AQUI = Path(__file__).resolve().parent
CUERPO = AQUI / "v2/salidas/h_vivo_eric"  # los tramos del cuerpo (V2)
SAL = AQUI / "v3/salidas"
LADO = 512
PROMPT_CARA = (
    "Close-up of a character whose head is a carved orange pumpkin with black headphones, "
    "speaking into a black studio microphone. His carved mouth is very expressive: it opens wide, "
    "stretches into a wicked grin, tightens and snaps shut with the words, and his carved brows "
    "frown and lift. He tilts his head with dark humor, like a horror host telling a story. "
    "Candle light flickers on the pumpkin skin. Cinematic close-up."
)


GRISES = [
    "mano_s77",
    "base",
    "inclinado_s7",
    "atras_s7",
    "ladeado_s77",
]  # las poses, antes de la cripta
POSES = AQUI / "poses/salidas"
ANCHO, ALTO = 832, 480  # el encuadre de V2 (LTX devuelve 832 × 448: se lleva con la escala)


def cabeza_en_inicio(k: int) -> tuple[float, float, float, float]:
    """La cabeza medida en la pose con fondo gris (confiable) y llevada al encuadre del tramo."""
    gris = Image.open(POSES / f"{GRISES[k]}.png").convert("RGB")
    cripta = Image.open(POSES / f"{GRISES[k]}_cripta.png").convert("RGB")
    rect = A.encuadre_rect(cripta, ANCHO, ALTO, 0.42)
    return A.llevar(A.zonas(gris).cabeza, rect, ANCHO, ALTO)


def cuadrado(caja, ancho, alto) -> tuple[int, int, int, int]:
    """El primer plano: un cuadrado alrededor de la cabeza (con el tallo y los auriculares)."""
    x0, y0, x1, y1 = caja
    lado = 1.6 * max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 0.1 * lado
    return round(cx - lado / 2), round(cy - lado / 2), round(cx + lado / 2), round(cy + lado / 2)


def recortar(im: Image.Image, caja) -> Image.Image:
    lienzo = Image.new("RGB", (caja[2] - caja[0], caja[3] - caja[1]), (8, 8, 8))
    lienzo.paste(im, (-caja[0], -caja[1]))
    return lienzo.resize((LADO, LADO), Image.Resampling.LANCZOS)


def mascara_cabeza(tam, caja) -> Image.Image:
    """Elipse que toma la calabaza, el tallo y los auriculares, con el borde suave."""
    x0, y0, x1, y1 = caja
    w, h = x1 - x0, y1 - y0
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).ellipse(
        (x0 - 0.12 * w, y0 - 0.22 * h, x1 + 0.12 * w, y1 + 0.02 * h), fill=255
    )
    return m.filter(ImageFilter.GaussianBlur(max(3, w * 0.06)))


def componer(
    cuerpo_mp4: Path, cara_mp4: Path, cab: tuple, sq: tuple, destino: Path, tmp: Path
) -> Path:
    """`cab`: la cabeza en el cuadro del cuerpo (cuadro 0); `sq`: el cuadrado del primer plano en
    esas mismas coordenadas. Se sigue la cabeza en los dos clips y la cara entra donde está."""
    cs = [Image.open(f).convert("RGB") for f in A.cuadros_de(cuerpo_mp4, tmp / "c", fps=V2.FPS_LTX)]
    fs = [Image.open(f).convert("RGB") for f in A.cuadros_de(cara_mp4, tmp / "f", fps=V2.FPS_LTX)]
    n = min(len(cs), len(fs))
    W, H = cs[0].size
    sy = H / ALTO  # 480 → 448 de LTX
    cab = (cab[0], cab[1] * sy, cab[2], cab[3] * sy)
    sq = (sq[0], sq[1] * sy, sq[2], sq[2] - sq[0] + sq[1] * sy)
    lado = sq[2] - sq[0]
    f2c = lado / fs[0].width  # de la cara (512) al cuerpo
    cab_f = tuple((v - o) / f2c for v, o in zip(cab, (sq[0], sq[1], sq[0], sq[1]), strict=True))
    mov_c = A.seguir(cs[:n], cab)
    mov_f = A.seguir(fs[:n], cab_f, radio=48)
    salida = tmp / "o"
    salida.mkdir(exist_ok=True)
    for i in range(n):
        c = cs[i]
        fz = fs[i].resize((round(lado), round(lado)), Image.Resampling.LANCZOS)
        dx = round(sq[0] + mov_c[i][0] - mov_f[i][0] * f2c)
        dy = round(sq[1] + mov_c[i][1] - mov_f[i][1] * f2c)
        capa = c.copy()
        capa.paste(fz, (dx, dy))
        caja = (
            cab[0] + mov_c[i][0],
            cab[1] + mov_c[i][1],
            cab[2] + mov_c[i][0],
            cab[3] + mov_c[i][1],
        )
        m = mascara_cabeza(c.size, caja)
        duro = m.point(lambda v: 255 if v > 20 else 0)
        anillo = ImageChops.subtract(duro.filter(ImageFilter.MaxFilter(9)), duro)
        capa = igualar(capa, c, anillo)
        Image.composite(capa, c, m).save(salida / f"o_{i:04d}.png")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-framerate",
            str(V2.FPS_LTX),
            "-i",
            str(salida / "o_%04d.png"),
            "-c:v",
            "libx264",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            str(destino),
        ],
        check=True,
    )
    shutil.rmtree(tmp, ignore_errors=True)
    return destino


async def main(semilla: int = 11) -> None:
    SAL.mkdir(parents=True, exist_ok=True)
    corrida = json.loads((CUERPO / "corrida.json").read_text())
    c = A.ClienteVideo()
    await c.liberar()
    compuestos = []
    for i, t in enumerate(corrida["tramos"]):
        k = t["pose"]
        inicio = Image.open(CUERPO / f"inicio_{k}.png").convert("RGB")
        cab = cabeza_en_inicio(k)
        sq = cuadrado(cab, ANCHO, ALTO)
        recortar(inicio, sq).save(SAL / f"cara_inicio_{i}.png")
        cara = SAL / f"cara_{i}_s{semilla}.mp4"
        if not cara.exists():
            med = await c.clip(
                "ltx",
                {
                    "prompt": PROMPT_CARA,
                    "segundos": round(t["hasta"] - t["desde"], 3),
                    "ancho_1": LADO // 2,
                    "alto_1": LADO // 2,
                    "cuadros": t["cuadros"],
                    "semilla": semilla,
                    "prefijo": f"spec810/v3_{i}",
                },
                {"imagen": SAL / f"cara_inicio_{i}.png", "audio": CUERPO / f"tramo_{i}.wav"},
                cara,
            )
            print(f"cara {i}: {med}", flush=True)
        comp = componer(
            CUERPO / f"tramo_{i}_s{t['semilla']}.mp4",
            cara,
            cab,
            sq,
            SAL / f"tramo_{i}_compuesto.mp4",
            SAL / f"_tmp_{i}",
        )
        compuestos.append(comp)
        print(f"tramo {i} compuesto", flush=True)
    await c.liberar()
    final = A.dirigir(
        compuestos,
        CUERPO / "audio.wav",
        SAL / "calabaza_cara_pegada.mp4",
        832,
        448,
        ["medio", "cerrado", "medio", "lateral", "medio"],
    )
    print(final)


asyncio.run(main())
