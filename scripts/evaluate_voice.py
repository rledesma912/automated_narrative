"""Evaluación de la prosa de la Voz con «El monte prohibido» (Spec-470 §2).

Genera N relatos por variante (sin / con entidades) con el perfil activo, en una DB
temporal y dentro de este proceso (la app FastAPI corre en memoria: no toca dev ni
prod), guarda cada relato y un `metrics.json`, e imprime una tabla.

    uv run python scripts/evaluate_voice.py --label antes --runs 2 --out <dir>
    uv run python scripts/evaluate_voice.py --label despues-t05 --variants con \\
        --voz-temperature 0.5 --out <dir>

`--voz-temperature` cambia la temperatura de la Voz solo dentro de este proceso.
`--mock` usa el LLM simulado (para probar el arnés sin Ollama).
"""

import argparse
import asyncio
import copy
import json
import sys
import tempfile
import uuid
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.voice_metrics import evaluate  # noqa: E402
from src.config import settings  # noqa: E402
from src.infrastructure.database.connection import init_db  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

STORY_FILE = Path(__file__).resolve().parents[1] / "input_stories" / "el_monte_prohibido.yaml"

# Las entidades de la evaluación de Spec-450 S5 (constante: evaluación reproducible).
ENTITIES = [
    {
        "name": "La Sombra del Monte",
        "nature": "folklorica",
        "description": "Un ser del monte que toma la forma de alguien querido para atraer a los "
        "que cruzan de noche; quiere quedarse con uno de la familia.",
        "manifestations": "El caballo se clava de golpe; una figura idéntica a María que no "
        "parpadea; olor a tierra mojada; un silencio que apaga los grillos.",
        "limits": "Los rezos la alejan; no puede cruzar el umbral de una casa con una vela "
        "encendida.",
        "reveal_level": "insinuada",
    },
    {
        "name": "El Monte de los Espinillos",
        "nature": "lugar",
        "description": "El monte mismo, que no quiere dejar salir a los que entran de noche.",
        "manifestations": "El camino se deforma; los mismos espinillos retorcidos aparecen una y "
        "otra vez; las espinas se enganchan en la ropa.",
        "limits": "Solo retiene de noche; al amanecer vuelve a ser un monte común.",
        "reveal_level": "progresiva",
    },
]

METRICS = ("cliches", "parentescos_mal", "narrador_3ra_persona", "frases_repetidas", "palabras")


def load_story(variant: str) -> dict:
    story = yaml.safe_load(STORY_FILE.read_text(encoding="utf-8"))
    if variant == "con":
        story = copy.deepcopy(story)
        story["storyteller_config"]["entities"] = ENTITIES
    return story


def narrator_of(story: dict) -> str:
    sc = story.get("storyteller_config") or {}
    if sc.get("storyteller_name"):
        return sc["storyteller_name"]
    pid = sc.get("storyteller_id")
    cast = story.get("personajes_full") or []
    return next((p["name"] for p in cast if p.get("id") == pid), cast[0]["name"] if cast else "")


async def _generate(client: httpx.AsyncClient, story: dict) -> str:
    from src.presentation.runtime import job_manager

    resp = await client.post("/api/v1/stories?action=save", json=story)
    resp.raise_for_status()
    job = (await client.post(f"/api/v1/stories/{resp.json()['id']}/jobs", json={})).json()
    await job_manager.wait(uuid.UUID(job["job_id"]))
    done = (await client.get(f"/api/v1/jobs/{job['job_id']}")).json()
    if done["status"] != "done":
        raise RuntimeError(f"La generación falló: {done.get('error')}")
    narrative = (await client.get(f"/api/v1/generated-narratives/{done['narrative_id']}")).json()
    return narrative["content"]


async def run(
    label: str,
    variants: list[str],
    runs: int,
    out: Path,
    voz_temperature: float | None = None,
    mock: bool = False,
) -> dict:
    """Genera y mide. Restaura al final todo lo que parchea (DB, LLM, temperatura)."""
    from src.main import app

    out = out / label
    out.mkdir(parents=True, exist_ok=True)
    settings_cls = type(settings)
    saved = (settings.database_url, LLMFactory.get_provider, settings_cls.role_config)
    if mock:
        from src.infrastructure.adapters import MockLLMAdapter

        LLMFactory.get_provider = staticmethod(lambda *_a, **_k: MockLLMAdapter())
    if voz_temperature is not None:
        original = settings_cls.role_config

        def role_config(self, role):
            cfg = dict(original(self, role))
            if role == "voz":
                cfg["temperature"] = voz_temperature
            return cfg

        settings_cls.role_config = role_config

    report: dict = {
        "label": label,
        "perfil": settings.active_profile_name,
        "voz_temperature": settings.role_config("voz").get("temperature"),
        "relatos": [],
    }
    try:
        with tempfile.TemporaryDirectory() as tmp:
            settings.database_url = f"sqlite+aiosqlite:///{Path(tmp) / 'eval.db'}"
            await init_db()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test", timeout=None
            ) as client:
                for variant in variants:
                    for i in range(1, runs + 1):
                        story = load_story(variant)
                        story["title"] = f"{story['title']} ({label} {variant} #{i})"
                        text = await _generate(client, story)
                        (out / f"{variant}_{i}.txt").write_text(text, encoding="utf-8")
                        metrics = evaluate(
                            text, narrator_of(story), story.get("personajes_full") or []
                        )
                        report["relatos"].append({"variante": variant, "corrida": i, **metrics})
                        print(f"  {label} {variant} #{i}: " + _row(metrics), flush=True)
    finally:
        settings.database_url, LLMFactory.get_provider, settings_cls.role_config = saved

    report["promedios"] = {
        v: {m: _avg([r[m] for r in report["relatos"] if r["variante"] == v]) for m in METRICS}
        for v in variants
    }
    (out / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _row(m: dict) -> str:
    return ", ".join(f"{k}={m[k]}" for k in METRICS)


def print_table(report: dict) -> None:
    print(f"\n{report['label']} — perfil {report['perfil']}, Voz T={report['voz_temperature']}")
    print(
        "| Variante | Clichés | Parentescos mal | Narradora 3ra persona | Frases repetidas | Palabras |"
    )
    print("|---|---|---|---|---|---|")
    for v, m in report["promedios"].items():
        print(
            f"| {v} | {m['cliches']} | {m['parentescos_mal']} | {m['narrador_3ra_persona']} "
            f"| {m['frases_repetidas']} | {m['palabras']} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--variants", default="sin,con")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--voz-temperature", type=float, default=None)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(
        run(
            args.label,
            [v.strip() for v in args.variants.split(",") if v.strip()],
            args.runs,
            args.out,
            args.voz_temperature,
            args.mock,
        )
    )
    print_table(report)


if __name__ == "__main__":
    main()
