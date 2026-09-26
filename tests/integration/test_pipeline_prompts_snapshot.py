"""Los prompts del pipeline (escaleta → Voz + memoria) no cambian sin querer.

Corre el job completo de la API con un LLM que graba cada llamada (sin escaleta:
primero la arma el Planificador) y compara los prompts contra un snapshot.

Regenerar el snapshot (solo si el cambio de texto es intencional):
    SNAPSHOT_UPDATE=1 uv run pytest tests/integration/test_pipeline_prompts_snapshot.py
"""

import json
import os
import uuid
from pathlib import Path

import httpx

from src.config import settings
from src.infrastructure.database.connection import init_db
from src.infrastructure.factories import LLMFactory
from src.main import app
from src.presentation.runtime import job_manager
from tests.support.recording_llm import RecordingLLM

SNAPSHOT = Path(__file__).parents[1] / "fixtures" / "snapshots" / "pipeline_prompts.json"

_ACTOS = {
    f"act_{n}": {"type": t, "text": f"Acto {n}: Rosa enfrenta algo en el galpón."}
    for n, t in enumerate(
        ["exposicion", "accion_ascendente", "climax", "accion_descendente", "desenlace"], 1
    )
}

STORY = {
    "title": "El galpón",
    "protagonista": "Rosa: peona [observadora]",
    "relator": "Primera persona en pasado. Narrador: Rosa. Registro: rural_tradicional.",
    "escenarios": "El galpón: chapas",
    "sinopsis": "\n\n".join(a["text"] for a in _ACTOS.values()),
    "genero": "folk_horror",
    "subgenero": "rural",
    "tono": "creciente",
    "reglas": ["Nadie entra de noche"],
    "narrator_config": {
        "storyteller_id": "P1",
        "storyteller_name": "Rosa",
        "voice_style": "intimista",
        "scenarios": [{"name": "El galpón", "description": "chapas oxidadas"}],
        "rules": [{"id": "R1", "text": "Nadie entra de noche", "type": "fenomeno"}],
        "actos": _ACTOS,
        "perception": {"reliability": "subjetiva"},
    },
    "personajes_full": [{"id": "P1", "name": "Rosa", "role": "peona", "traits": ["observador"]}],
}


async def generate(monkeypatch, tmp_path, story: dict, llm: RecordingLLM) -> list[dict]:
    """Crea la historia, corre el job completo y devuelve las llamadas grabadas."""
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'p.db'}")
    monkeypatch.setattr(LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: llm))
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/stories?action=save", json=story)
        assert resp.status_code == 201, resp.text
        job = await client.post(f"/api/v1/stories/{resp.json()['id']}/jobs", json={})
        await job_manager.wait(uuid.UUID(job.json()["job_id"]))
        status = (await client.get(f"/api/v1/jobs/{job.json()['job_id']}")).json()
        assert status["status"] == "done", status
    return llm.calls


async def test_prompts_del_pipeline_no_cambian(monkeypatch, tmp_path):
    calls = await generate(monkeypatch, tmp_path, STORY, RecordingLLM())

    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(calls, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert calls == json.loads(SNAPSHOT.read_text("utf-8"))
