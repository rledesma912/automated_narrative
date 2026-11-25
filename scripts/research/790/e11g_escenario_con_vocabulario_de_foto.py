"""Spike E11g: con la IA mirando los bocetos (T6.5), la tanda 5 salió «de dibujo»: la IA describe
las hojas como están dibujadas y Z-Image deja las siluetas planas. ¿Si la IA nombra lo que hay
con vocabulario de foto (tipo de planta real, niebla en capas) vuelve la atmósfera de la tanda 4
sin la persona sentada? Usa el código del arnés tal cual; solo cambia el párrafo de los bocetos."""

import asyncio
import json
import shutil
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comun import grilla  # noqa: E402

from src.application.services.miniatura import arte as arte_  # noqa: E402
from src.application.services.miniatura import textos as textos_  # noqa: E402
from src.application.services.miniatura.arnes import Arnes, _hash  # noqa: E402
from src.domain.thumbnail import Thumbnail, ThumbnailInput  # noqa: E402
from src.infrastructure.adapters.comfy.client import ComfyClient  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

SID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
C = RAIZ / "data/dev/miniaturas" / SID
AQUI = Path(__file__).resolve().parent / "e11g"
SAL = AQUI / "salidas"
SEMILLAS = [int(_hash(SID), 16) % 1_000_000, 11]
PARRAFO_T65 = (RAIZ / "scripts/research/790/e11e/ia_sistema_con_bocetos.md").read_text().strip()
PARRAFO_FOTO = (AQUI / "ia_sistema_foto.md").read_text().strip()


def sistema_con(parrafo: str) -> str:
    base = arte_.texto("ia_sistema")  # desde T6.6 ya trae el párrafo de E11g
    actual = PARRAFO_T65 if PARRAFO_T65 in base else PARRAFO_FOTO
    assert actual in base
    return base.replace(actual, parrafo)


async def main():
    SAL.mkdir(parents=True, exist_ok=True)
    i = json.load(urllib.request.urlopen(f"http://localhost:8040/api/v1/stories/{SID}/thumbnail"))["input"]
    llm = LLMFactory.get_provider()
    filas = [("tanda 5", [("qwen", C / "piezas/escenario_crudo.png"), ("foto", C / "piezas/escenario.png")])]
    variante = "foto"
    textos_json = SAL / f"textos_{variante}.json"
    sistema = sistema_con(PARRAFO_FOTO)
    original = textos_.texto
    textos_.texto = lambda paso, **d: sistema if paso == "ia_sistema" else original(paso, **d)
    for s in SEMILLAS:
        carpeta = SAL / f"{variante}_s{s}"
        (carpeta / "bocetos").mkdir(parents=True, exist_ok=True)
        for b in ("personaje", "escenario"):
            shutil.copy(C / "bocetos" / Path(i[f"{'character' if b == 'personaje' else 'scene'}_sketch"]).name,
                        carpeta / "bocetos" / f"{b}.png")
        thumb = Thumbnail(story_id=SID, input=ThumbnailInput(**{**i, "character_sketch": "bocetos/personaje.png", "scene_sketch": "bocetos/escenario.png"}))
        if textos_json.exists():
            from src.domain.thumbnail import ImageTexts
            thumb.texts = ImageTexts(**json.loads(textos_json.read_text()))
        arnes = Arnes(ComfyClient(), carpeta, llm=llm)
        if thumb.texts is None:
            txt = await textos_.separar(llm, thumb.input, "e11g", [carpeta / "bocetos/personaje.png", carpeta / "bocetos/escenario.png"])
            textos_json.write_text(json.dumps(txt.model_dump(), ensure_ascii=False, indent=1))
        else:
            txt = thumb.texts
        print(txt.escenario, flush=True)
        if not (carpeta / "piezas/escenario.png").exists():
            await arnes.escenario(thumb, s, txt.escenario)
        filas.append((f"{variante} s{s}", [("qwen", carpeta / "piezas/escenario_crudo.png"), ("foto", carpeta / "piezas/escenario.png")]))
    await ComfyClient().liberar()
    print(grilla(filas, SAL / "grilla.png", ancho_celda=640))


asyncio.run(main())
