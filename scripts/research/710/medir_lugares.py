"""Spec-710: ¿el Planificador da un lugar por hecho, sin compuestos, cosas ni nombres de código?

S5: corre el Planificador real (`OutlinePlanner`, prompts de `config/`) con el perfil
activo (`hibrido-sonnet55`: desde la Spec-720, Sonnet 5.5) sobre historias de la copia
de prod. Anota el lugar tal cual lo devolvió la IA (antes de `_lugar()`) y el que queda.
(La medición de §9, con gemma y una variante del prompt que vivía acá, quedó en
`data/dev/research_710/gemma_2.json`.)

No toca la base. Sin `--yes` solo estima; `--tope` corta lo pago.

    uv run python scripts/research/710/medir_lugares.py <salida.json> [--yes] [--tope 0.6]

La salida va a data/dev/research_710/ (fuera de git: son historias reales).
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("LLM_PROFILE", "hibrido-sonnet55")

from scripts.evaluate_voice import TokenMeter  # noqa: E402
from src.application.services.authoring import planner  # noqa: E402
from src.application.services.authoring.planner import OutlinePlanner  # noqa: E402
from src.infrastructure.database.repositories import SQLStoryRepository  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

HISTORIAS = [
    "El trabajo de Yadira",
    "Los forasteros",
    "el engaño del diablo",
    "No es tu culpa",
    "El último cliente",
    "La criatura del río Paraná",
]
ESTIMADO = 0.05  # por historia, solo el Planificador (Spec-720 §11: ~0,04–0,05)
COMPUESTO = re.compile(r",|/| - | y ", re.I)


async def main(args) -> None:
    out = Path(args.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Costo estimado: US$ {ESTIMADO * len(HISTORIAS):.2f} (tope US$ {args.tope:.2f})")
    if not args.yes:
        print("Sin --yes no se corre nada pago.")
        return

    crudos: list[str] = []
    original = planner._lugar

    def anotar(name: str) -> str:
        crudos.append(name)
        return original(name)

    planner._lugar = anotar

    repo = SQLStoryRepository()
    by_title = {s.title: s for s in await repo.list_all()}
    rows, gastado = [], 0.0
    for title in HISTORIAS:
        if gastado + ESTIMADO > args.tope:
            print(f"Tope: US$ {gastado:.3f}; corto antes de {title}")
            break
        crudos.clear()
        llm = TokenMeter(LLMFactory.get_provider())
        story = await repo.get_by_id(by_title[title].id)
        start = time.monotonic()
        acts, _ = await OutlinePlanner(llm).plan(story)
        costo = llm.cost_usd()
        gastado += costo
        hechos = [(a.number, e, a.event_places[i]) for a in acts for i, e in enumerate(a.events)]
        # `_lugar` se llama por hecho y una vez más por el escenario del acto (el primero).
        raw = [c for c in crudos]
        rows.append(
            {
                "historia": title,
                "hechos": len(hechos),
                "sin_lugar": sum(1 for _, _, p in hechos if not p),
                "crudos": list(dict.fromkeys(raw)),
                "compuestos": sorted({r for r in raw if COMPUESTO.search(r)}),
                "codigo": sorted({r for r in raw if "_" in r}),
                "lugares": list(dict.fromkeys(p for a in acts for p in a.places())),
                "actos": [
                    {
                        "numero": a.number,
                        "hechos": [[e, a.event_place(i)] for i, e in enumerate(a.events)],
                    }
                    for a in acts
                ],
                "segundos": round(time.monotonic() - start, 1),
                "costo_usd": round(costo, 4),
            }
        )
        r = rows[-1]
        print(
            f"{title[:28]:28} hechos={r['hechos']} sin_lugar={r['sin_lugar']} "
            f"compuestos={len(r['compuestos'])} codigo={len(r['codigo'])} "
            f"lugares={len(r['lugares'])} {r['segundos']}s US$ {costo:.3f}",
            flush=True,
        )
        print(f"    {' · '.join(r['lugares'])}")
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        await llm.close()
    print(f"Gastado: US$ {gastado:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("salida")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--tope", type=float, default=0.6)
    asyncio.run(main(parser.parse_args()))
