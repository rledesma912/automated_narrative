"""Spec-610 T2.5: el job `video_script` arma el paquete con el mock y se lee por la API."""

import asyncio
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.domain.models import GeneratedNarrative
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLGeneratedNarrativeRepository
from src.infrastructure.factories import LLMFactory
from src.main import app

_PAYLOAD = {
    "title": "No te detengas en el bosque",
    "protagonista": "Ernesto: camionero",
    "relator": "Primera persona en pasado. Narrador: Ernesto.",
    "escenarios": "El bosque: la ruta",
    "sinopsis": "Un camión se queda en el bosque.",
}
CONTENT = "\n\n".join(
    f"## Acto {a}\n\n" + "\n\n".join(f"Párrafo {p} del acto {a}." for p in range(1, 4))
    for a in range(1, 6)
)


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'vs.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: MockLLMAdapter())
    )
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _narrative(client) -> GeneratedNarrative:
    resp = await client.post("/api/v1/stories?action=save", json=_PAYLOAD)
    assert resp.status_code in (200, 201), resp.text
    return await SQLGeneratedNarrativeRepository().save(
        GeneratedNarrative(
            story_template_id=uuid.UUID(resp.json()["id"]), title="v1", content=CONTENT
        )
    )


async def _wait_job(client, job_id: str) -> dict:
    for _ in range(100):
        job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        if job["status"] in ("done", "failed"):
            return job
        await asyncio.sleep(0.05)
    raise AssertionError("el job no terminó")


async def test_armar_el_paquete_y_leerlo(client):
    narrative = await _narrative(client)
    url = f"/api/v1/generated-narratives/{narrative.id}/video-script"
    assert (await client.get(url)).status_code == 404

    resp = await client.post(
        f"/api/v1/stories/{narrative.story_template_id}/jobs",
        json={"kind": "video_script", "narrative_id": str(narrative.id)},
    )
    assert resp.status_code == 202, resp.text
    job = await _wait_job(client, resp.json()["job_id"])
    assert job["status"] == "done", job
    assert job["params"]["narrative_id"] == str(narrative.id)

    paquete = (await client.get(url)).json()
    assert paquete["lector"] == "Lucas"
    assert len(paquete["bloques"]) == 15
    assert paquete["parrafos_por_acto"] == {str(n): 3 for n in range(1, 6)}


async def test_sin_relato_o_de_otra_historia(client):
    narrative = await _narrative(client)
    url = f"/api/v1/stories/{narrative.story_template_id}/jobs"
    sin = await client.post(url, json={"kind": "video_script"})
    assert sin.status_code == 422
    otro = await client.post(url, json={"kind": "video_script", "narrative_id": str(uuid.uuid4())})
    assert otro.status_code == 404
