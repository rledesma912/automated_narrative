"""Un ComfyUI de mentira para los tests de las miniaturas (Spec-790): sin GPU ni red.

- `boceto_a_imagen` y `foto_img2img` devuelven la entrada (a ~1392 × 752 si es un boceto);
- `recortar` devuelve una máscara con una elipse blanca al centro (la «figura» o lo importante).
"""

from pathlib import Path

from PIL import Image, ImageDraw


class FakeComfy:
    def __init__(self, vram: float = 12000):
        self.vram = vram
        self.llamadas: list[str] = []

    async def vram_libre_mb(self) -> float:
        return self.vram

    async def liberar(self) -> None:
        self.llamadas.append("liberar")

    async def correr(
        self, receta: str, valores: dict, entradas: dict[str, Path], destino: Path
    ) -> Path:
        self.llamadas.append(receta)
        destino.parent.mkdir(parents=True, exist_ok=True)
        entrada = Image.open(next(iter(entradas.values()))).convert("RGB")
        if receta == "recortar":
            m = Image.new("L", entrada.size, 0)
            w, h = entrada.size
            ImageDraw.Draw(m).ellipse((w * 0.35, h * 0.05, w * 0.65, h * 0.98), fill=255)
            m.save(destino)
        else:
            entrada.save(destino)
        return destino
