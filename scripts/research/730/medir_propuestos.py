"""Spec-730 S4: ¿qué personajes suma Sonnet, con qué para qué, y respeta el tope?

Corre el Planificador y el Verificador reales con el perfil activo (`hibrido-sonnet55`:
desde la 720 los dos en Sonnet 5.5) sobre historias de la copia de prod. Anota lo que
la IA pidió sumar (crudo) y lo que entró (`planner.propuestos`), los nombres que quedan
con el aviso de siempre (`elenco:`) y los avisos de la IA que repiten el de personajes.
No guarda nada en la base. Sin `--yes` solo estima; `--tope` corta lo pago.

    uv run python scripts/research/730/medir_propuestos.py <salida.json> [--yes] [--tope 0.5]

La salida va a data/dev/research_730/ (fuera de git: son historias reales).
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
from src.application.services.authoring import elenco, planner  # noqa: E402
from src.application.services.authoring.planner import OutlinePlanner  # noqa: E402
from src.application.services.authoring.verifier import OutlineVerifier  # noqa: E402
from src.infrastructure.database.repositories import SQLStoryRepository  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

HISTORIAS = ["El trabajo de Yadira", "Los forasteros", "el engaño del diablo", "El último cliente"]
ESTIMADO = 0.06  # por historia (Planificador + Verificador, Spec-720 §11)
DUPLICADO = re.compile(r"no (figura|está) (en el elenco|entre (los|tus) personajes)", re.I)


async def main(args) -> None:
    out = Path(args.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Costo estimado: US$ {ESTIMADO * len(HISTORIAS):.2f} (tope US$ {args.tope:.2f})")
    if not args.yes:
        print("Sin --yes no se corre nada pago.")
        return

    # Lo que pidió la IA, antes del filtro de `elenco.propuestos`.
    crudo: list = []
    original = elenco.propuestos

    def anotar(story, acts, pedidos, maximo):
        crudo[:] = [p.model_dump() for p in pedidos]
        return original(story, acts, pedidos, maximo)

    planner.elenco.propuestos = anotar

    repo = SQLStoryRepository()
    by_title = {s.title: s for s in await repo.list_all()}
    rows, gastado = [], 0.0
    for title in HISTORIAS:
        if gastado + ESTIMADO > args.tope:
            print(f"Tope: US$ {gastado:.3f}; corto antes de {title}")
            break
        llm = TokenMeter(LLMFactory.get_provider())
        story = await repo.get_by_id(by_title[title].id)
        start = time.monotonic()
        plan = OutlinePlanner(llm)
        acts, _ = await plan.plan(story)
        nuevos = plan.propuestos
        story = elenco.con_personajes(
            story,
            elenco.personajes_de_la_autora(story, acts) + [p.nombre for p in nuevos],
            {p.nombre: p.quien_es for p in nuevos},
        )
        checked = await OutlineVerifier(llm).verify(story, acts)
        avisos = [w for a in checked.outline for w in a.warnings]
        costo = llm.cost_usd()
        gastado += costo
        rows.append(
            {
                "historia": title,
                "estructura": story.structure,
                "pedidos": crudo[:],
                "propuestos": [p.__dict__ for p in nuevos],
                "elenco": sorted({w.subject for w in avisos if w.key.startswith("elenco:")}),
                "duplicados_ia": [
                    w.text for w in avisos if w.key.startswith("ia:") and DUPLICADO.search(w.text)
                ],
                "en_escena": {a.number: a.on_stage for a in acts},
                "segundos": round(time.monotonic() - start, 1),
                "costo_usd": round(costo, 4),
            }
        )
        r = rows[-1]
        print(
            f"{title[:26]:26} pedidos={len(r['pedidos'])} propuestos={len(r['propuestos'])} "
            f"elenco={len(r['elenco'])} duplicados={len(r['duplicados_ia'])} "
            f"{r['segundos']}s US$ {costo:.3f}",
            flush=True,
        )
        for p in r["propuestos"]:
            print(f"    + {p['nombre']} ({p['quien_es']}): {p['para_que']} [acto {p['acto']}]")
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        await llm.close()
    print(f"Gastado: US$ {gastado:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("salida")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--tope", type=float, default=0.5)
    asyncio.run(main(parser.parse_args()))
