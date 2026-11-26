"""La hoja de presentación de las tres ideas de cuerpo (Spec-800, H1a segunda vuelta).

Python arma la lámina (texto, paleta, las tres figuras) y la publica en el tablero junto con
las opciones sueltas para votar.

    uv run python scripts/research/800/h1a2_presentacion.py <anfitrion.png> <sepulturero.png> <planta.png> [--prod]
"""

import shutil
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
from src.application.services.tablero.entregas import publicar  # noqa: E402

AQUI = Path(__file__).resolve().parent
SAL = AQUI / "h1a3/salidas"  # con la cabeza que eligió Yael
FUENTES = RAIZ / "assets/fonts"
W, H = 2400, 1640
FONDO, TINTA, SUAVE, VIOLETA = (20, 17, 15), (236, 226, 208), (170, 158, 140), (150, 90, 230)

IDEAS = [
    (
        "1 · El anfitrión",
        "Mi propuesta",
        [
            "Levita de terciopelo raída, forro violeta",
            "Chaleco con botones de bronce y reloj",
            "La enredadera asoma por cuello y puños",
        ],
    ),
    (
        "2 · El sepulturero",
        "Más sobria",
        [
            "Capa larga con capucha caída",
            "Chaleco, cinturón de cuero viejo",
            "Botas altas gastadas",
        ],
    ),
    (
        "3 · La planta",
        "Más monstruo",
        [
            "El cuerpo es enredadera y raíces",
            "Levita con forro violeta",
            "Raíces en vez de pies",
        ],
    ),
]
PALETA = [
    ((14, 12, 12), "Negro cripta"),
    ((222, 112, 34), "Calabaza"),
    ((120, 60, 200), "Violeta de los ojos"),
    ((86, 96, 58), "Verde musgo"),
    ((150, 112, 60), "Bronce gastado"),
]


def fuente(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FUENTES / nombre), tam)


def main(figuras: list[Path], prod: bool) -> None:
    hoja = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(hoja)
    titulo, sub = fuente("Literata-Variable.ttf", 92), fuente("Literata-Italic-Variable.ttf", 40)
    nombre, cuerpo = (
        fuente("AtkinsonHyperlegible-Bold.ttf", 44),
        fuente("AtkinsonHyperlegible-Regular.ttf", 32),
    )
    chico = fuente("AtkinsonHyperlegible-Italic.ttf", 28)

    d.text((100, 70), "La calabaza de la cripta", font=titulo, fill=TINTA)
    d.text(
        (104, 190),
        "Lleva siglos en su cripta contando historias… y hace poco descubrió el micrófono.",
        font=sub,
        fill=SUAVE,
    )
    d.text(
        (104, 250),
        "Tres ideas para su cuerpo. La cabeza, los ojos y el micrófono no cambian.",
        font=cuerpo,
        fill=VIOLETA,
    )

    col_w, top, alto_img = 700, 330, 900
    for i, (ruta, (n, etiqueta, puntos)) in enumerate(zip(figuras, IDEAS, strict=True)):
        x = 100 + i * (col_w + 50)
        im = Image.open(ruta).convert("RGB")
        im = im.resize((round(im.width * alto_img / im.height), alto_img), Image.LANCZOS)
        if im.width > col_w:
            m = (im.width - col_w) // 2
            im = im.crop((m, 0, m + col_w, alto_img))
        hoja.paste(im, (x + (col_w - im.width) // 2, top))
        y = top + alto_img + 24
        d.text((x, y), n, font=nombre, fill=TINTA)
        d.text((x + d.textlength(n, font=nombre) + 18, y + 12), etiqueta, font=chico, fill=VIOLETA)
        for j, p in enumerate(puntos):
            d.text((x, y + 66 + j * 42), f"·  {p}", font=cuerpo, fill=SUAVE)

    y = H - 70
    x = 100
    for color, nom in PALETA:
        d.rounded_rectangle((x, y - 8, x + 44, y + 36), radius=6, fill=color, outline=(70, 64, 58))
        d.text((x + 58, y), nom, font=chico, fill=SUAVE)
        x += 58 + d.textlength(nom, font=chico) + 50
    nota = "Inspirada en los anfitriones de los cuentos de terror, con un diseño propio."
    d.text((100, y - 70), nota, font=chico, fill=SUAVE)

    entrega = AQUI / "h1a2/2026-11-26-calabaza-tres-ideas"
    shutil.rmtree(entrega, ignore_errors=True)
    entrega.mkdir(parents=True)
    hoja.save(entrega / "presentacion.jpg", quality=92)
    shutil.copy(SAL / "ojos_py_70_200.png", entrega / "ojos.png")
    imagenes = []
    for ruta, (n, _, _) in zip(figuras, IDEAS, strict=True):
        shutil.copy(ruta, entrega / ruta.name)
        imagenes.append({"archivo": ruta.name, "leyenda": n})
    datos = {
        "titulo": "La calabaza de la cripta: tres ideas para su cuerpo",
        "proyecto": "calabaza",
        "que_mirar": (
            "La calabaza como **anfitrión de la cripta**: una calabaza vieja que cuenta historias "
            "desde hace siglos y que hace poco descubrió el micrófono. La ropa es de otra época; "
            "lo único moderno es su equipo de audio.\n\n"
            "- La cabeza es **la que eligió Yael**, igual en las tres. Los ojos, como pidió: **cuencas negras** con la pupila violeta más chica y tenue, y el brillo que se escapa por el cuello.\n"
            "- Marcá 👍 en la idea que te guste y contá con 💬 qué le cambiarías.\n"
            "- Es una primera prueba: la cara, la pose y la luz se afinan después."
        ),
        "filas": [
            {
                "titulo": "La presentación",
                "imagenes": [{"archivo": "presentacion.jpg", "leyenda": "Las tres ideas"}],
            },
            {"titulo": "Las tres ideas, para votar", "imagenes": imagenes},
            {
                "titulo": "Los ojos, como pidió Yael",
                "imagenes": [
                    {
                        "archivo": "ojos.png",
                        "leyenda": "La cabeza de Yael: cuencas negras, pupila tenue",
                    }
                ],
            },
        ],
    }
    (entrega / "entrega.yaml").write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False)
    )
    e = publicar(
        entrega, RAIZ / ("data/prod/tablero" if prod else "data/dev/tablero"), reemplazar=True
    )
    print(f"/tablero/{e.id}")


main([Path(a) for a in sys.argv[1:4]], "--prod" in sys.argv)
