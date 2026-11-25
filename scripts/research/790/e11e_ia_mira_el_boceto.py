"""Spike E11e: la IA de texto (GPT-5.6 Sol) mira los dos bocetos además de los textos de Yael.
¿Su descripción del escenario nombra la planta del centro y saca la silueta de persona?"""

import asyncio
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy, grilla  # noqa: E402
from e1_personaje import grafo_qwen, grafo_zimage  # noqa: E402
from e3c_oscuro import curva  # noqa: E402

RAIZ = AQUI.parents[2]
SID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
C = RAIZ / "data/dev/miniaturas" / SID
P = RAIZ / "config/miniatura/prompts"
SAL = AQUI / "e11e" / "salidas"
SEM = [990851, 11]


def b64(ruta: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(ruta.read_bytes()).decode()


async def textos() -> dict:
    destino = SAL / "textos.json"
    if destino.exists():
        return json.loads(destino.read_text())
    i = json.load(urllib.request.urlopen(f"http://localhost:8040/api/v1/stories/{SID}/thumbnail"))["input"]
    sistema = (P / "ia_sistema.md").read_text() + "\n\n" + (AQUI / "e11e/ia_sistema_con_bocetos.md").read_text()
    pedido = (P / "ia_pedido.md").read_text().replace("{personaje}", i["figure_description"]).replace(
        "{lugar}", i["place_description"])
    esquema = {
        "type": "object",
        "properties": {
            "personaje": {"type": "string"},
            "escenario": {"type": "string"},
            "relacion": {"type": "string"},
            "a_medio_ver": {"type": "string", "enum": ["no", "poco", "mucho"]},
        },
        "required": ["personaje", "escenario", "relacion", "a_medio_ver"],
        "additionalProperties": False,
    }
    cli = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    r = await cli.chat.completions.create(
        model="gpt-5.6-sol",
        reasoning_effort="none",
        max_completion_tokens=2000,
        response_format={"type": "json_schema", "json_schema": {"name": "textos", "strict": True, "schema": esquema}},
        messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": [
                {"type": "text", "text": pedido},
                {"type": "image_url", "image_url": {"url": b64(C / "bocetos/personaje.png")}},
                {"type": "image_url", "image_url": {"url": b64(C / "bocetos/escenario.png")}},
            ]},
        ],
    )
    out = json.loads(r.choices[0].message.content)
    out["_tokens"] = [r.usage.prompt_tokens, r.usage.completion_tokens]
    destino.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


async def main():
    SAL.mkdir(parents=True, exist_ok=True)
    t = await textos()
    print(json.dumps(t, ensure_ascii=False, indent=1), flush=True)
    qwen_p = (P / "escenario.md").read_text().strip().replace("{descripcion}", t["escenario"])
    foto_p = (P / "fotografiar_escenario.md").read_text().strip().replace("{descripcion}", t["escenario"])
    async with Comfy() as c:
        boceto = await c.subir(C / "bocetos/escenario.png")
        for s in SEM:
            d = SAL / f"qwen_s{s}.png"
            if not d.exists():
                r = await c.correr(grafo_qwen(boceto, qwen_p, s, f"spec790/e11e/q_{s}"))
                await c.bajar(r.imagenes[0], d)
        await c.liberar()
        for s in SEM:
            d = SAL / f"foto_s{s}.png"
            if not d.exists():
                osc = curva(SAL / f"qwen_s{s}.png", SAL / f"oscuro_s{s}.png")
                r = await c.correr(grafo_zimage(foto_p, s, f"spec790/e11e/z_{s}", await c.subir(osc), 0.45))
                await c.bajar(r.imagenes[0], d)
        await c.liberar()
    filas = [
        ("tanda 4", [("qwen", C / "piezas/escenario_crudo.png"), ("foto", C / "piezas/escenario.png")]),
        ("con boceto s990851", [("qwen", SAL / "qwen_s990851.png"), ("foto", SAL / "foto_s990851.png")]),
        ("con boceto s11", [("qwen", SAL / "qwen_s11.png"), ("foto", SAL / "foto_s11.png")]),
    ]
    print(grilla(filas, SAL / "grilla.png", ancho_celda=640))


asyncio.run(main())
