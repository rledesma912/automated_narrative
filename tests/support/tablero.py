"""Entregas de prueba para el tablero (Spec-795)."""

from pathlib import Path

import yaml
from PIL import Image

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'


def png(ruta: Path, color=(90, 60, 120)) -> Path:
    Image.new("RGB", (40, 30), color).save(ruta)
    return ruta


def entrega(base: Path, id_: str = "2026-11-26-calabaza-hoja", **cambios) -> Path:
    """Una entrega válida con una fila de dos PNG y un SVG suelto."""
    carpeta = base / id_
    carpeta.mkdir(parents=True)
    png(carpeta / "a.png")
    png(carpeta / "b.png", (20, 20, 20))
    (carpeta / "vistas.svg").write_text(SVG)
    datos = {
        "titulo": "La calabaza, primera hoja",
        "proyecto": "calabaza",
        "que_mirar": "Elegí la que más se parece.\n\n- **A** más contraste\n- B más parecida",
        "filas": [
            {
                "titulo": "Maestra",
                "imagenes": [
                    {"archivo": "a.png", "leyenda": "A"},
                    {"archivo": "b.png", "leyenda": "B"},
                ],
            }
        ],
        "imagenes": [{"archivo": "vistas.svg", "leyenda": "Cómo se arma"}],
        **cambios,
    }
    (carpeta / "entrega.yaml").write_text(yaml.safe_dump(datos, allow_unicode=True))
    return carpeta
