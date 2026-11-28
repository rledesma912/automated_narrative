"""Spec-820 S2: la IA de la nube (rol `miniatura`) escribe un prompt por plantilla mirando los
bocetos y miniaturas de Yael como referencia de luz. Las imágenes las sigue haciendo Z-Image.

  set -a; . ./.env; set +a; PYTHONPATH=. uv run python scripts/research/820/s2_prompts.py
"""

import asyncio
import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.miniatura.textos import boceto_para_la_ia
from src.infrastructure.factories import LLMFactory

ID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
AQUI = Path(__file__).parent
REF = AQUI / "salidas" / "referencias"


class _Prompt(BaseModel):
    plantilla: str
    prompt: str
    luz: str


class _Salida(BaseModel):
    prompts: list[_Prompt]


async def main():
    d = json.loads(
        sqlite3.connect("data/dev/stories.db")
        .execute("select data from thumbnail where story_id=?", (ID,))
        .fetchone()[0]
    )
    i, t = d["input"], d["texts"]
    pedido = (
        f"CÓMO ES EL PERSONAJE (lo escribió la ilustradora):\n{i['figure_description']}\n\n"
        f"CÓMO ES EL LUGAR:\n{i['place_description']}\n\n"
        f"CÓMO ESTÁN JUNTOS: {t['relacion']}\n\n"
        "IMÁGENES, en orden: 1) boceto del personaje, 2) boceto del lugar, 3–6) miniaturas de "
        "referencia del canal (solo la luz).\n\n"
        "Plantillas: A_der, A_izq, C_primer_plano, B_lugar."
    )
    base = Path(f"data/dev/miniaturas/{ID}")
    imgs = [
        base / i["character_sketch"],
        base / i["scene_sketch"],
        REF / "peter_yael.jpg",
        REF / "yael_3.jpg",
        REF / "yael_9.jpg",
        REF / "yael_15.jpg",
    ]
    llm = LLMFactory.get_provider()
    r, _ = await generate_structured(
        llm,
        role="miniatura",
        prompt=pedido,
        system_prompt=(AQUI / "prompts" / "s2_sistema.md").read_text(),
        output=_Salida,
        images=[boceto_para_la_ia(p) for p in imgs],
    )
    out = {p.plantilla: {"prompt": " ".join(p.prompt.split()), "luz": p.luz} for p in r.prompts}
    (AQUI / "salidas" / "s2_prompts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for k, v in out.items():
        print(f"== {k} ({len(v['prompt'].split())} palabras)\n{v['prompt']}\n→ {v['luz']}\n")


if __name__ == "__main__":
    asyncio.run(main())
