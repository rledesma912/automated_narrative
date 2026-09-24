"""Mide los prompts de cada rol con 0, 1 y 3 entidades contra el num_ctx del perfil (Spec-450 T3.5).

Corre el pipeline real (job de la API, DB temporal) con un LLM que responde con
textos de tamaño realista, y cuenta los tokens de cada llamada (system + user)
con el tokenizer del modelo del rol vía Ollama (`prompt_eval_count`). Sin Ollama,
`--heuristic` estima 1 token cada 3,2 caracteres.

Ollama reserva la salida dentro del mismo contexto: el margen se calcula como
num_ctx - (prompt + num_predict).

    uv run python scripts/measure_entity_prompts.py [--heuristic]
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import settings  # noqa: E402
from src.domain.interfaces import LLMResponse  # noqa: E402
from src.infrastructure.database.connection import init_db  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

ROLES = ("story_analyst", "director", "voz", "journal")
WORDS = "el monte cerrado guarda un silbido que baja con la siesta y deja olor a azufre".split()


def words(n: int) -> str:
    return " ".join(WORDS[i % len(WORDS)] for i in range(n))


_ACTS = ["exposicion", "accion_ascendente", "climax", "accion_descendente", "desenlace"]
STORY = {
    "title": "El monte prohibido",
    "protagonista": "Irene: nuera; Ricardo: esposo; María: suegra",
    "relator": "Primera persona en pasado. Narrador: Irene. Registro: rural_tradicional.",
    "escenarios": "",
    "sinopsis": "\n\n".join(f"Acto {n}: {words(110)}." for n in range(1, 6)),
    "genero": "folk_horror",
    "subgenero": "rural",
    "tono": "creciente",
    "reglas": [words(14) for _ in range(5)],
    "narrator_config": {
        "storyteller_id": "P1",
        "storyteller_name": "Irene",
        "voice_style": "intimista",
        "scenarios": [{"name": f"Escenario {i}", "description": words(20)} for i in range(1, 4)],
        "rules": [{"id": f"R{i}", "text": words(14), "type": "fenomeno"} for i in range(1, 6)],
        "actos": {
            f"act_{n}": {"type": t, "text": f"Acto {n}: {words(110)}."}
            for n, t in enumerate(_ACTS, 1)
        },
        "perception": {"reliability": "subjetiva"},
    },
    "personajes_full": [
        {"id": f"P{i}", "name": name, "role": words(8), "traits": ["observador", "miedoso"]}
        for i, name in enumerate(["Irene", "Ricardo", "María"], 1)
    ],
}


def entity(i: int) -> dict:
    """Entidad con todos los campos al tope de largo."""
    return {
        "name": ("Entidad " + words(12))[:60],
        "nature": ["folklorica", "culto", "espiritu"][i],
        "description": words(90)[:400],
        "manifestations": words(70)[:300],
        "limits": words(70)[:300],
        "reveal_level": "progresiva",
    }


class RealisticLLM:
    """Responde con largos realistas y guarda cada llamada."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def generate(self, prompt: str, *, system_prompt: str | None = None, role=None, **_kw):
        self.calls.append({"role": role, "system": system_prompt or "", "prompt": prompt})
        if role == "story_analyst":
            text = "\n\n".join(
                f"## {k}\n{words(70)}"
                for k in (
                    "resonance_hamartia",
                    "resonance_hybris",
                    "resonance_anagnorisis",
                    "resonance_peripeteia",
                    "resonance_residual",
                )
            )
        elif role == "director":
            text = "ESCENARIO: Escenario 1\nEVENTOS:\n" + "\n".join(
                f"- {words(20)}." for _ in range(6)
            )
        elif role == "journal":
            text = json.dumps(
                {
                    "last_events": words(30),
                    "unresolved_mysteries": words(30),
                    "physical_emotional_state": words(30),
                    "entity_state": words(40),
                },
                ensure_ascii=False,
            )
        else:
            text = words(500)
        return LLMResponse(text=text, context=None)

    async def close(self) -> None:
        pass


async def run_pipeline(story: dict) -> list[dict]:
    from src.main import app
    from src.presentation.runtime import job_manager

    llm = RealisticLLM()
    LLMFactory.get_provider = staticmethod(lambda *_a, **_k: llm)
    with tempfile.TemporaryDirectory() as tmp:
        settings.database_url = f"sqlite+aiosqlite:///{Path(tmp) / 'm.db'}"
        await init_db()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/stories?action=save", json=story)
            resp.raise_for_status()
            job = (await client.post(f"/api/v1/stories/{resp.json()['id']}/jobs", json={})).json()
            await job_manager.wait(uuid.UUID(job["job_id"]))
    return llm.calls


def count_tokens(call: dict, model: str, heuristic: bool) -> int:
    if heuristic:
        return round((len(call["system"]) + len(call["prompt"])) / 3.2)
    host = settings.ollama_host
    resp = httpx.post(
        f"{host}/api/generate",
        json={
            "model": model,
            "system": call["system"],
            "prompt": call["prompt"],
            "stream": False,
            "options": {"num_predict": 1, "num_ctx": 32768},
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["prompt_eval_count"]


async def main(heuristic: bool) -> None:
    scenarios = {
        "0 entidades": STORY,
        "1 entidad": {**copy.deepcopy(STORY)},
        "3 entidades": {**copy.deepcopy(STORY)},
    }
    scenarios["1 entidad"]["narrator_config"]["entities"] = [entity(0)]
    scenarios["3 entidades"]["narrator_config"]["entities"] = [entity(i) for i in range(3)]

    rows = []
    for label, story in scenarios.items():
        calls = await run_pipeline(story)
        for role in ROLES:
            cfg = settings.role_config(role)
            role_calls = [c for c in calls if c["role"] == role]
            if not role_calls:
                continue
            tokens = max(count_tokens(c, cfg.get("model", ""), heuristic) for c in role_calls)
            ctx, out = int(cfg.get("num_ctx", 4096)), int(cfg.get("num_predict", 2048))
            rows.append((label, role, tokens, out, ctx, ctx - tokens - out))

    method = "heurística (3,2 caracteres/token)" if heuristic else "tokenizer del modelo (Ollama)"
    print(f"Perfil: {settings.active_profile_name} · conteo: {method}\n")
    print("| Escenario | Rol | Prompt máx. | Salida (num_predict) | num_ctx | Margen |")
    print("|---|---|---|---|---|---|")
    for label, role, tokens, out, ctx, margin in rows:
        flag = " ⚠" if margin < 0 else ""
        print(f"| {label} | {role} | {tokens} | {out} | {ctx} | {margin}{flag} |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--heuristic", action="store_true", help="Estimar sin Ollama")
    asyncio.run(main(parser.parse_args().heuristic))
