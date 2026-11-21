"""Spec-760 S3 y Spec-770 S2: ¿cuánto de una idea larga llega a los actos que arma la IA, según el largo?

Trabaja sobre una **copia** de la base (nunca la de prod). La copia ya trae los actos
del Corto de cada historia. Para cada una mide ese Corto, la pasa a Media
(`PUT …/structure`), arma y revisa los actos con la IA del perfil activo
(`plan_outline`, que ya trae la revisión) y mide de nuevo.

    uv run python scripts/research/760/medir_ideas_largas.py \
        --db <copia.db> --stories <id,id,…> --out scripts/research/760/resultados.json [--mock]

La medición no usa IA. **Eco** de una oración de la idea (de más de 6 palabras): la
proporción de sus palabras de 5 letras o más que aparecen en los hechos. Con ≥ 40 % la
oración cuenta como «con eco». Es una cuenta gruesa: sirve para comparar, no para medir
fino. El resultado guarda solo números: **ningún texto de las autoras**.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.evaluate_voice import PRICES  # noqa: E402
from src.config import settings  # noqa: E402
from src.infrastructure.database.connection import init_db  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402
from src.main import app  # noqa: E402
from src.presentation.runtime import job_manager  # noqa: E402

API = "/api/v1"
_PALABRA = re.compile(r"\w{5,}")
_ORACION = re.compile(r"(?<=[.!?])\s+")
ECO_MIN = 0.4


def palabras(texto: str) -> set[str]:
    return set(_PALABRA.findall(texto.lower()))


def oraciones(idea: str) -> list[str]:
    return [o for o in _ORACION.split(idea) if len(o.split()) > 6]


def eco(idea: str, hechos: list[str]) -> tuple[int, int]:
    """(oraciones con eco, oraciones) de la idea en los hechos."""
    en_hechos = palabras(" ".join(hechos))
    ors = oraciones(idea)
    con = sum(1 for o in ors if (p := palabras(o)) and len(p & en_hechos) / len(p) >= ECO_MIN)
    return con, len(ors)


def medir(state: dict) -> dict:
    acts = state["outline"]["acts"]
    hechos = [h for a in acts for h in a["events"]]
    idea = state["direction"]["premise"]
    con, total = eco(idea, hechos)
    return {
        "estructura": state["structure"],
        "idea_palabras": len(idea.split()),
        "hechos_por_acto": [len(a["events"]) for a in acts],
        "palabras_de_hechos": len(" ".join(hechos).split()),
        "eco": round(con / total, 3) if total else None,
        "oraciones_con_eco": f"{con}/{total}",
        "avisos_visibles": sum(1 for a in acts for w in a["warnings"] if not w["dismissed"]),
        "final_en_el_ultimo": _final_en_el_ultimo(state),
        # Spec-770: el hecho más largo y cuánto de los hechos no sale de la autora.
        "hecho_mas_largo": max((len(h) for h in hechos), default=0),
        "palabras_nuevas": _nuevas(state, hechos),
    }


def _nuevas(state: dict, hechos: list[str]) -> float | None:
    """Spec-770 A3: palabras (de 5 letras o más) de los hechos que no están en nada de lo
    que escribió la autora (idea, respuestas, personajes, lugares). Cuánto inventa."""
    autora = [state["direction"]["premise"]]
    autora += [i.get("answer") or "" for i in state["workshop"]["items"]]
    autora += [c["name"] + " " + (c.get("relation") or "") for c in state["characters"]]
    autora += [s["name"] for s in state["scenarios"]]
    en_hechos = palabras(" ".join(hechos))
    if not en_hechos:
        return None
    return round(len(en_hechos - palabras(" ".join(autora))) / len(en_hechos), 3)


def _final_en_el_ultimo(state: dict) -> bool | None:
    final = next((i for i in state["workshop"]["items"] if i["criterion"] == "final"), None)
    if not final or not final.get("answer"):
        return None
    ultimo = state["outline"]["acts"][-1]["events"]
    p = palabras(final["answer"])
    return bool(p) and len(p & palabras(" ".join(ultimo))) / len(p) >= ECO_MIN


async def job(client: httpx.AsyncClient, sid: str, kind: str) -> dict:
    resp = await client.post(f"{API}/stories/{sid}/jobs", json={"kind": kind})
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    data = (await client.get(f"{API}/jobs/{job_id}")).json()
    if data["status"] != "done":
        raise RuntimeError(f"{kind}: {data['status']} {data.get('error')}")
    return data


def costo(db: Path, sids: list[str]) -> dict:
    import sqlite3

    conn = sqlite3.connect(db)
    marks = ",".join("?" * len(sids))
    rows = conn.execute(
        "SELECT role, model, sum(input_tokens), sum(output_tokens), sum(elapsed_s), count(*)"
        f" FROM llm_call WHERE story_id IN ({marks}) AND created_at > ?"
        " GROUP BY role, model",
        [*sids, _INICIO],
    ).fetchall()
    total = 0.0
    por_rol = {}
    for role, model, tin, tout, secs, n in rows:
        pin, pout = PRICES.get(model, (0, 0))
        usd = ((tin or 0) * pin + (tout or 0) * pout) / 1_000_000
        total += usd
        por_rol[role] = {
            "modelo": model,
            "llamadas": n,
            "tokens_entrada": tin,
            "tokens_salida": tout,
            "segundos": round(secs or 0, 1),
            "usd": round(usd, 4),
        }
    return {"usd_total": round(total, 3), "por_rol": por_rol}


_INICIO = ""


async def main() -> None:
    global _INICIO
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--stories", required=True, help="ids separados por coma")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument(
        "--estructura",
        default="medio",
        help="en qué largo se rearma (si es el de la historia, se rearma en el mismo)",
    )
    args = parser.parse_args()
    if "data/prod" in str(args.db.resolve()):
        sys.exit("Esto se corre sobre una copia, nunca sobre la base de prod.")

    settings.database_url = f"sqlite+aiosqlite:///{args.db}"
    if args.mock:
        from src.infrastructure.adapters import MockLLMAdapter

        LLMFactory.get_provider = staticmethod(lambda *_a, **_k: MockLLMAdapter())
    await init_db()
    from datetime import datetime

    _INICIO = datetime.now().astimezone().isoformat()

    sids = args.stories.split(",")
    resultados = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=600
    ) as client:
        for n, sid in enumerate(sids, 1):
            state = (await client.get(f"{API}/authoring/stories/{sid}")).json()
            antes = medir(state)
            if state["structure"] != args.estructura:
                resp = await client.put(
                    f"{API}/authoring/stories/{sid}/structure",
                    json={"structure": args.estructura},
                )
                resp.raise_for_status()
            await job(client, sid, "plan_outline")  # arma y revisa (el Verificador va adentro)
            despues = medir((await client.get(f"{API}/authoring/stories/{sid}")).json())
            resultados.append(
                {"historia": f"idea {n}", "antes": antes, f"ia_{args.estructura}": despues}
            )
            print(json.dumps(resultados[-1], ensure_ascii=False))

    salida = {
        "perfil": "mock" if args.mock else (settings.llm_profile or os.getenv("LLM_PROFILE", "")),
        "eco_min": ECO_MIN,
        "resultados": resultados,
        "costo": costo(args.db, sids),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(salida["costo"], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
