# ruff: noqa: N806, F841, B023  (spike: nombres de imagen en mayúscula, como en la 790)
"""Spec-820 S1b (pedido del usuario, 2026-11-27): despegar la criatura del fondo, ojos que brillen,
escala contra los árboles y «Manda el lugar» a un costado.

- Composición: la de S0 (tanda 9) para A_der, A_izq y C; para B_lugar se recompone con la figura
  más chica y a un costado. En todas: un halo de niebla clara detrás de la figura y los ojos
  marcados en amarillo.
- Guía de profundidad: la figura cerca (blanco) y el halo lejos (negro): el corte que la despega.
- Después: BiRefNet marca la figura en la foto y Python aclara apenas la niebla del anillo.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

from src.application.services.miniatura import imagen
from src.application.services.miniatura.arte import Plantilla, arte
from src.infrastructure.adapters.comfy.client import ComfyClient

sys.path.insert(0, str(Path(__file__).parent))
from control import controlar, luz  # noqa: E402

ID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
BASE = Path(f"data/dev/miniaturas/{ID}")
AQUI = Path(__file__).parent
OUT = (
    AQUI / "salidas" / (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("s") else "s1b")
)
MODO = {  # respeta en las A, reinterpreta en C y B (decisión del usuario)
    "A_der": (0.62, 0.60),
    "A_izq": (0.62, 0.60),
    "C_primer_plano": (0.80, 0.50),
    "B_lugar": (0.80, 0.55),
}
B_NUEVA = Plantilla(nombre="Manda el lugar", cx=0.70, alto=0.40, recorte=1.0)
HALO = (232, 236, 240)
import os  # noqa: E402

# S2: los prompts que escribió la IA de la nube (si se pasa S2_PROMPTS); si no, el fijo.
PROMPTS = (
    json.loads(Path(os.environ["S2_PROMPTS"]).read_text()) if os.environ.get("S2_PROMPTS") else None
)
# S1c: el tronco que tapa a la criatura en A_der (el que puso Qwen en la tanda 8). En el spike se
# marca a mano; en el flujo, Python lo sabe porque compone él el tronco.
TRONCO = {"A_der": [(665, 0), (975, 0), (960, 300), (985, 720), (560, 720), (600, 400)]}
DETRAS = (
    " It is half-hidden behind the thick dark tree trunk in the foreground: the trunk passes"
    " in front of its body, one clawed hand grips the bark, and its head and glowing eyes"
    " peek out from behind the trunk."
)


def ojos(rgb: Image.Image, alfa: Image.Image) -> Image.Image:
    """Lo muy claro y cálido dentro de la figura (los ojos), como máscara."""
    claro = ImageOps.grayscale(rgb).point(lambda v: 255 if v > 170 else 0)
    return ImageChops.multiply(claro, alfa.point(lambda v: 255 if v > 128 else 0))


def composicion_b() -> tuple[Image.Image, Image.Image, Image.Image]:
    """B_lugar de nuevo: el escenario con luz (S0 sin figura) y la figura chica a la derecha."""
    A = arte()
    fondo = imagen.lienzo(Image.open(BASE / "piezas" / "escenario.png"), A)
    tmp = OUT / "b_fondo_sin_luz.png"
    fondo.save(tmp)
    # la luz de S0 sobre el escenario solo (alfa vacía)
    import importlib.util

    spec = importlib.util.spec_from_file_location("s0", AQUI / "s0_luz_python.py")
    L = ImageOps.autocontrast(fondo.convert("L"), cutoff=1)
    W, H = fondo.size
    vert = (
        Image.linear_gradient("L")
        .resize((W, H))
        .point(lambda v: int(255 * max(0.25, min(1, 1.25 - (v / 255) ** 2 * 1.3))))
    )
    lejos = L.filter(ImageFilter.GaussianBlur(40)).point(
        lambda v: int(255 * min(1, max(0, (v - 30) / 90)))
    )
    fogm = ImageChops.multiply(vert, lejos).point(lambda v: int(v * 0.85))
    bg = Image.composite(
        Image.new("L", (W, H), 200), L.point(lambda v: int(v * 0.55)), fogm
    ).convert("RGB")
    fig = imagen.con_alfa(
        Image.open(BASE / "piezas" / "personaje.png"),
        Image.open(BASE / "piezas" / "personaje_mascara.png"),
    )
    fig = imagen.figura_recortada(fig, 1.0)
    f, pos = imagen.ubicar(fig, B_NUEVA, imagen.apoyo(fig), A)
    alfa = imagen.alfa_en_cuadro(f, pos, A)
    color = Image.new("RGB", (W, H))
    color.paste(f.convert("RGB"), pos)
    sil = color.convert("L").point(lambda v: min(55, int(v * 0.3))).convert("RGB")
    comp = Image.composite(sil, bg, alfa.filter(ImageFilter.GaussianBlur(1.5)))
    return comp, alfa, ojos(color, alfa)


def con_halo(comp: Image.Image, alfa: Image.Image, ojos_m: Image.Image) -> Image.Image:
    H = comp.height
    duro = alfa.point(lambda v: 255 if v > 128 else 0)
    halo = imagen.dilatar(duro, round(0.10 * H)).filter(ImageFilter.GaussianBlur(0.06 * H))
    halo = ImageChops.subtract(halo, duro).point(lambda v: int(v * 0.75))
    out = Image.composite(Image.new("RGB", comp.size, HALO), comp, halo)
    amarillo = Image.new("RGB", comp.size, (255, 215, 70))
    return Image.composite(
        amarillo, out, imagen.dilatar(ojos_m, 2).filter(ImageFilter.GaussianBlur(1.5))
    )


def mascara_tronco(t: str, tam) -> Image.Image | None:
    if t not in TRONCO:
        return None
    from PIL import ImageDraw

    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).polygon(TRONCO[t], fill=255)
    return m.filter(ImageFilter.GaussianBlur(2))


def profundidad(comp: Image.Image, alfa: Image.Image, tronco=None) -> Image.Image:
    H = comp.height
    duro = alfa.point(lambda v: 255 if v > 128 else 0)
    lejos = ImageOps.invert(ImageOps.grayscale(comp).filter(ImageFilter.GaussianBlur(6)))
    lejos = ImageOps.autocontrast(lejos, cutoff=1).point(lambda v: round(255 * (v / 255) ** 2.2))
    anillo = imagen.dilatar(duro, round(0.07 * H)).filter(ImageFilter.GaussianBlur(0.03 * H))
    lejos = Image.composite(Image.new("L", comp.size, 0), lejos, anillo)
    cerca = Image.composite(
        Image.new("L", comp.size, 225 if tronco else 255),
        lejos,
        alfa.filter(ImageFilter.GaussianBlur(2)),
    )
    if tronco is not None:  # el tronco es lo más cercano: tapa a la figura
        cerca = Image.composite(Image.new("L", comp.size, 255), cerca, tronco)
    return cerca.convert("RGB")


def despegar(foto: Image.Image, mascara: Image.Image) -> Image.Image:
    """Después: aclarar apenas la niebla que rodea a la figura (no la figura)."""
    H = foto.height
    m = mascara.convert("L").resize(foto.size).point(lambda v: 255 if v > 128 else 0)
    anillo = ImageChops.subtract(
        imagen.dilatar(m, round(0.05 * H)).filter(ImageFilter.GaussianBlur(0.04 * H)), m
    )
    claro = ImageChops.screen(foto, Image.new("RGB", foto.size, (90, 95, 100)))
    out = Image.composite(claro, foto, anillo.point(lambda v: int(v * 0.6)))
    # mate: dentro de la figura las luces se aplastan (sin brillo húmedo ni de plástico),
    # salvo los ojos (lo cálido y muy claro). El borde (luz de contorno) queda.
    nucleo = imagen.erosionar(m, round(0.012 * H)).filter(ImageFilter.GaussianBlur(3))
    techo = 70
    mate = out.point(
        lambda v: v if v < techo * 0.6 else round(techo * 0.6 + (v - techo * 0.6) * 0.25)
    )
    ojos_m = imagen.dilatar(imagen.acentos(foto), 3).filter(ImageFilter.GaussianBlur(2))
    nucleo = ImageChops.subtract(nucleo, ojos_m)
    return Image.composite(mate, out, nucleo)


async def main(plantillas, semilla):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tanda").mkdir(exist_ok=True)
    datos = json.loads((AQUI / "salidas" / "textos.json").read_text())
    texto = (AQUI / "prompts" / "una_foto_v2.md").read_text().strip().format(**datos)
    c = ComfyClient()
    for t in plantillas:
        if t == "B_lugar":
            comp, alfa, ojos_m = composicion_b()
        else:
            comp = Image.open(BASE / "tanda_9" / f"{t}.jpg").convert("RGB")
            alfa = Image.open(BASE / "tanda_8" / f"{t}_alfa.png").convert("L")
            ojos_m = ojos(Image.open(BASE / "tanda_8" / f"{t}_sin_color.png").convert("RGB"), alfa)
        tronco = mascara_tronco(t, comp.size)
        comp = con_halo(comp, alfa, ojos_m)
        if tronco is not None:  # la corteza de la tanda 8, oscura, por delante del halo
            corteza = (
                Image.open(BASE / "tanda_8" / f"{t}_sin_color.png")
                .convert("L")
                .point(lambda v: int(v * 0.6))
            )
            comp = Image.composite(corteza.convert("RGB"), comp, tronco)
        comp.save(OUT / f"{t}_comp.png")
        profundidad(comp, alfa, tronco).save(OUT / f"{t}_guia.png")
        cambio, fuerza = MODO[t]
        t0 = time.time()
        foto = await c.correr(
            "foto_controlnet",
            {
                "prompt": (
                    PROMPTS[t]["prompt"]
                    if PROMPTS
                    else texto + (DETRAS if tronco is not None else "")
                ),
                "semilla": semilla,
                "cambio": cambio,
                "fuerza": fuerza,
                "prefijo": "spec820/s1b",
            },
            {"imagen": OUT / f"{t}_comp.png", "guia": OUT / f"{t}_guia.png"},
            OUT / f"{t}_foto.png",
        )
        seg = round(time.time() - t0, 1)
        A = arte()
        ctrl = controlar(Image.open(foto).convert("RGB"))
        ctrl.save(OUT / f"{t}_ctrl.png")
        masc = await c.correr(
            "recortar",
            {"prefijo": "spec820/s1b_m"},
            {"imagen": OUT / f"{t}_ctrl.png"},
            OUT / f"{t}_mascara.png",
        )
        final = despegar(ctrl, Image.open(masc))
        final.save(OUT / "tanda" / f"{t}.jpg", quality=90)
        print(t, {"cambio": cambio, "fuerza": fuerza, "segundos": seg, **luz(final)}, flush=True)
    await c.liberar()


if __name__ == "__main__":
    asyncio.run(main([a for a in sys.argv[1:] if not a.startswith("s")] or list(MODO), 820))
