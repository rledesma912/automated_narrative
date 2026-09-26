"""Medición de la Spec-530 (S6): pipeline de siempre vs. asistente con escaleta.

Para cada historia de referencia y cada corrida:
- «base»: la historia tal como la carga el wizard (sinopsis), pipeline de siempre;
- «asistente»: la misma historia con una Dirección, una ronda del taller en la que el
  «autor» responde todo con «Decidí vos» (reproducible), la escaleta revisada y el
  relato generado desde la escaleta.

Corre en una DB temporal y dentro de este proceso (no toca dev ni prod), con el perfil
activo. Guarda cada relato y un `metrics.json`, e imprime una tabla.

    uv run python scripts/evaluate_workshop.py --runs 2 --out <dir>
    uv run python scripts/evaluate_workshop.py --runs 1 --stories pena --mock   # probar el arnés
"""

import argparse
import asyncio
import json
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.voice_metrics import evaluate, split_acts  # noqa: E402
from src.application.services.repetition_check import check  # noqa: E402
from src.config import settings  # noqa: E402
from src.domain.models import Direction  # noqa: E402
from src.infrastructure.database.connection import init_db  # noqa: E402
from src.infrastructure.database.repositories import SQLStoryRepository  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

STORIES = {
    "pena": {
        "file": ROOT / "scripts" / "research" / "530" / "pena.yaml",
        "direction": Direction(
            effect="pavor",
            ending="José le deja flores y el alma de la mujer descansa en paz: no la vuelve a ver.",
            ending_intentional=True,
            telling="caso",
        ),
    },
    "monte": {
        "file": ROOT / "input_stories" / "el_monte_prohibido.yaml",
        "direction": Direction(effect="pavor", telling="confesion"),
    },
}
METRICS = (
    "segundos",
    "palabras",
    "cliches",
    "frases_repetidas",
    "nombres_inventados",
    "narrador_3ra_persona",
    "parentescos_mal",
)


async def _wait_job(
    client: httpx.AsyncClient, story_id: str, kind: str | None
) -> tuple[dict, float]:
    from src.presentation.runtime import job_manager

    body = {"kind": kind} if kind else {}
    t0 = time.perf_counter()
    resp = await client.post(f"/api/v1/stories/{story_id}/jobs", json=body)
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    if job["status"] != "done":
        raise RuntimeError(f"{kind or 'full_generation'} falló: {job.get('error')}")
    return job, time.perf_counter() - t0


async def _create(client: httpx.AsyncClient, data: dict, title: str) -> str:
    resp = await client.post("/api/v1/stories?action=save", json={**data, "title": title})
    resp.raise_for_status()
    return resp.json()["id"]


async def _relato(client: httpx.AsyncClient, job: dict) -> str:
    return (await client.get(f"/api/v1/generated-narratives/{job['narrative_id']}")).json()[
        "content"
    ]


def _measure(text: str, story_data: dict, known: str) -> dict:
    cast = story_data.get("personajes_full") or []
    narrator = (story_data.get("storyteller_config") or {}).get("storyteller_name", "")
    base = evaluate(text, narrator, cast)
    reps = check(split_acts(text), known=known)
    return {
        "palabras": base["palabras"],
        "cliches": sum(len(r.cliches) for r in reps),
        "frases_repetidas": sum(len(r.repeated) for r in reps),
        "nombres_inventados": sum(len(r.invented_names) for r in reps),
        "narrador_3ra_persona": base["narrador_3ra_persona"],
        "parentescos_mal": base["parentescos_mal"],
        "palabras_por_acto": [len(a.split()) for a in split_acts(text)],
        "detalle": [
            {
                "acto": r.number,
                "repetidas": r.repeated,
                "cliches": r.cliches,
                "nombres": r.invented_names,
            }
            for r in reps
        ],
    }


def _known_text(story) -> str:
    from src.presentation.routers.narrative_router import _authoring_text

    return _authoring_text(story)


async def _run_base(client, key: str, data: dict, i: int, out: Path) -> dict:
    sid = await _create(client, data, f"{data['title']} (base #{i})")
    job, secs = await _wait_job(client, sid, None)
    text = await _relato(client, job)
    (out / f"{key}_base_{i}.md").write_text(text, encoding="utf-8")
    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))
    return {"segundos": round(secs), **_measure(text, data, _known_text(story))}


async def _run_asistente(client, key: str, data: dict, i: int, out: Path) -> dict:
    repo = SQLStoryRepository()
    sid = await _create(client, data, f"{data['title']} (asistente #{i})")
    direction = STORIES[key]["direction"].model_copy(update={"premise": data["sinopsis"]})
    await repo.update_direction(uuid.UUID(sid), direction)

    _, t_consult = await _wait_job(client, sid, "consult")
    state = (await client.get(f"/api/v1/authoring/stories/{sid}")).json()
    detected = {w["criterion"]: w["status"] for w in state["workshop"]["items"]}
    questions = [w["criterion"] for w in state["workshop"]["items"] if w["question"]]
    for criterion in questions:  # el «autor» delega todo: reproducible
        await client.patch(
            f"/api/v1/authoring/stories/{sid}/workshop/{criterion}", json={"action": "decide"}
        )

    _, t_plan = await _wait_job(client, sid, "plan_outline")
    state = (await client.get(f"/api/v1/authoring/stories/{sid}")).json()
    decisions = state["outline"]["decisions"]
    warnings = sum(len(a["warnings"]) for a in state["outline"]["acts"])
    (out / f"{key}_escaleta_{i}.json").write_text(
        json.dumps(state["outline"], ensure_ascii=False, indent=1), encoding="utf-8"
    )

    job, t_gen = await _wait_job(client, sid, None)
    text = await _relato(client, job)
    (out / f"{key}_asistente_{i}.md").write_text(text, encoding="utf-8")
    story = await repo.get_by_id(uuid.UUID(sid))
    return {
        "segundos": round(t_gen),
        "segundos_taller": round(t_consult),
        "segundos_escaleta": round(t_plan),
        "taller": detected,
        "decisiones_integradas": f"{sum(d['integrada'] for d in decisions)}/{len(decisions)}",
        "avisos_escaleta": warnings,
        **_measure(text, data, _known_text(story)),
    }


async def run(
    stories: list[str],
    runs: int,
    out: Path,
    mock: bool,
    variants: tuple[str, ...] = ("base", "asistente"),
) -> dict:
    from src.main import app

    out.mkdir(parents=True, exist_ok=True)
    saved = (settings.database_url, LLMFactory.get_provider)
    if mock:
        from src.infrastructure.adapters import MockLLMAdapter

        LLMFactory.get_provider = staticmethod(lambda *_a, **_k: MockLLMAdapter())
    report: dict = {"perfil": settings.active_profile_name, "corridas": []}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            settings.database_url = f"sqlite+aiosqlite:///{Path(tmp) / 'eval.db'}"
            await init_db()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://t", timeout=None
            ) as client:
                for key in stories:
                    data = yaml.safe_load(STORIES[key]["file"].read_text(encoding="utf-8"))
                    for i in range(1, runs + 1):
                        for variant, fn in (("base", _run_base), ("asistente", _run_asistente)):
                            if variant not in variants:
                                continue
                            m = await fn(client, key, data, i, out)
                            report["corridas"].append(
                                {"historia": key, "variante": variant, "corrida": i, **m}
                            )
                            print(f"  {key} {variant} #{i}: " + _row(m), flush=True)
    finally:
        settings.database_url, LLMFactory.get_provider = saved

    report["promedios"] = {
        f"{k}/{v}": {
            m: round(
                statistics.mean(
                    r[m] for r in report["corridas"] if r["historia"] == k and r["variante"] == v
                ),
                1,
            )
            for m in METRICS
        }
        for k in stories
        for v in variants
    }
    (out / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _row(m: dict) -> str:
    extra = ""
    if "decisiones_integradas" in m:
        extra = (
            f" | taller {m['segundos_taller']}s escaleta {m['segundos_escaleta']}s "
            f"decisiones {m['decisiones_integradas']} avisos {m['avisos_escaleta']}"
        )
    return ", ".join(f"{k}={m[k]}" for k in METRICS) + extra


def print_table(report: dict) -> None:
    print(f"\nPerfil: {report['perfil']}  (promedios)")
    print(f"{'historia/variante':22}" + "".join(f"{m[:14]:>16}" for m in METRICS))
    for key, row in report["promedios"].items():
        print(f"{key:22}" + "".join(f"{row[m]:>16}" for m in METRICS))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--stories", default="pena,monte")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mock", action="store_true", help="LLM simulado (probar el arnés)")
    parser.add_argument("--variants", default="base,asistente")
    args = parser.parse_args()
    stories = [s for s in args.stories.split(",") if s in STORIES]
    variants = tuple(v for v in args.variants.split(",") if v in ("base", "asistente"))
    print_table(asyncio.run(run(stories, args.runs, args.out, args.mock, variants)))


if __name__ == "__main__":
    main()
