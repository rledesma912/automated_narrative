"""Spike H1a (Spec-800): ¿Qwen-Edit saca una calabaza de cuerpo entero fiel desde las
referencias que hay (el avatar de 130 px y una captura de un video)?

La referencia va arriba de un lienzo vertical gris (2:3): Qwen-Edit devuelve la imagen con el
aspecto de la entrada, así que el lienzo vertical le pide el cuerpo entero. También se prueba la
referencia sola (cuadrada), para comparar. Publica todo en el tablero (dev; con --prod, en prod).

    set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 \\
    uv run python scripts/research/800/h1a_maestra.py [--prod]
"""

import asyncio
import shutil
import sys
from pathlib import Path

import yaml
from PIL import Image

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from src.application.services.tablero.entregas import publicar  # noqa: E402
from src.infrastructure.adapters.comfy.client import ComfyClient  # noqa: E402

AQUI = Path(__file__).resolve().parent
SAL = AQUI / "h1a/salidas"
CFG = yaml.safe_load((RAIZ / "config/personajes/calabaza.yaml").read_text())
PROMPT = (
    (RAIZ / "config/personajes/prompts/maestra.md").read_text().strip().format(fijo=CFG["fijo"])
)
SEMILLAS = [11, 222, 3333]
GRIS = (128, 128, 128)


def referencia(clave: str) -> Image.Image:
    im = Image.open(RAIZ / CFG["referencias"][clave]).convert("RGB")
    if clave == "video":
        im = im.crop((310, 40, 640, 518))  # la calabaza, sin el logo ni el botón del reproductor
    return im


def en_retrato(ref: Image.Image) -> Image.Image:
    """La referencia arriba y al centro de un lienzo 832 × 1248, el resto gris."""
    lienzo = Image.new("RGB", (832, 1248), GRIS)
    ancho = 460
    r = ref.resize((ancho, round(ref.height * ancho / ref.width)), Image.LANCZOS)
    lienzo.paste(r, ((832 - ancho) // 2, 40))
    return lienzo


def sola(ref: Image.Image) -> Image.Image:
    lado = 1024
    return ref.resize((lado, round(ref.height * lado / ref.width)), Image.LANCZOS)


async def main(prod: bool):
    SAL.mkdir(parents=True, exist_ok=True)
    c = ComfyClient()
    filas = []
    for clave, nombre in (("avatar", "Desde el avatar"), ("video", "Desde el video")):
        ref = referencia(clave)
        ref.save(SAL / f"ref_{clave}.png")
        entradas = {"retrato": en_retrato(ref), "sola": sola(ref)}
        celdas = [{"archivo": f"ref_{clave}.png", "leyenda": "La referencia"}]
        for modo, img in entradas.items():
            entrada = SAL / f"entrada_{clave}_{modo}.png"
            img.save(entrada)
            semillas = SEMILLAS if modo == "retrato" else SEMILLAS[:1]
            for s in semillas:
                d = SAL / f"{clave}_{modo}_s{s}.png"
                if not d.exists():
                    await c.correr(
                        "boceto_a_imagen", {"prompt": PROMPT, "semilla": s}, {"boceto": entrada}, d
                    )
                    print(d.name, flush=True)
                leyenda = (
                    f"{'Lienzo vertical' if modo == 'retrato' else 'Referencia sola'} · semilla {s}"
                )
                celdas.append({"archivo": d.name, "leyenda": leyenda})
        filas.append({"titulo": nombre, "imagenes": celdas})
    await c.liberar()

    entrega = AQUI / "h1a/2026-11-26-calabaza-h1a-maestra"
    shutil.rmtree(entrega, ignore_errors=True)
    entrega.mkdir(parents=True)
    for f in filas:
        for a in f["imagenes"]:
            shutil.copy(SAL / a["archivo"], entrega / a["archivo"])
    datos = {
        "titulo": "La calabaza, primera maestra (H1a)",
        "proyecto": "calabaza",
        "que_mirar": (
            "Primeras pruebas de la calabaza **de cuerpo entero**, en pose neutra, sacadas de las "
            "dos imágenes que tenemos: el avatar del canal y un cuadro de un video.\n\n"
            "- Marcá 👍 en la que **es** tu calabaza (aunque se vea chica: después se agranda).\n"
            "- Con 💬 contá qué está mal: la cara, el tallado, los auriculares, la ropa, el cuerpo.\n"
            "- «Lienzo vertical» le pide el cuerpo entero; «Referencia sola» es para comparar."
        ),
        "filas": filas,
    }
    (entrega / "entrega.yaml").write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False)
    )
    base = RAIZ / ("data/prod/tablero" if prod else "data/dev/tablero")
    e = publicar(entrega, base, reemplazar=True)
    print(f"Publicada en {'prod' if prod else 'dev'}: /tablero/{e.id}")


asyncio.run(main("--prod" in sys.argv))
