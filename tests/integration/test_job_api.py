"""Integración de la API de jobs y del SSE legado (Spec-460 S3).

App real (httpx + ASGITransport), DB temporal y MockLLMAdapter: el pipeline
completo corre de punta a punta sin Ollama.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from src.application.services.event_bus import job_channel
from src.config import settings
from src.domain.jobs import CANCELLED_ERROR
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter
from src.infrastructure.database.connection import get_connection, init_db
from src.infrastructure.factories import LLMFactory
from src.main import app
from src.presentation import generation
from src.presentation.runtime import event_bus, job_manager

_WIZARD_PAYLOAD = {
    "title": "La pena del colectivo",
    "protagonista": "José: conductor de micro [observador]",
    "relator": "Primera persona en pasado. Narrador: José.",
    "escenarios": "El micro: moderno",
    "sinopsis": "\n\n".join(f"Acto {n}: algo pasa en el micro." for n in range(1, 6)),
    "reglas": ["El micro trae casos paranormales"],
    "storyteller_config": {
        "storyteller_id": "P1",
        "atmosphere": {"genre": "horror_cosmico", "subgenre": "otro", "tone": "constante"},
        "scenarios": [{"name": "El micro", "description": "moderno"}],
        "rules": [{"id": "R1", "text": "El micro trae casos paranormales", "type": "entorno"}],
    },
    "personajes_full": [{"id": "P1", "name": "José", "role": "conductor", "traits": []}],
}


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: MockLLMAdapter())
    )
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def hold(monkeypatch) -> asyncio.Event:
    """Reemplaza el pipeline real por uno que espera hasta `hold.set()`."""
    block = asyncio.Event()

    def _runner(_story):
        async def _gen() -> AsyncIterator[StreamEvent]:
            yield StreamEvent(event=StreamEventType.STATUS, data={"msg": "esperando"})
            await block.wait()
            yield StreamEvent(event=StreamEventType.DONE, data={"narrative_id": None})

        return _gen

    monkeypatch.setattr(generation, "full_generation_runner", _runner)
    return block


async def _create_story(client: httpx.AsyncClient) -> str:
    resp = await client.post("/api/v1/stories?action=save", json=_WIZARD_PAYLOAD)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        fields: dict = {}
        for line in block.splitlines():
            if line.startswith(":") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            fields[key] = value.strip()
        if "event" in fields:
            fields["data"] = json.loads(fields.get("data") or "null")
            events.append(fields)
    return events


async def _job_rows(story_id: str) -> int:
    conn = await get_connection()
    cursor = await conn.execute(
        "SELECT COUNT(*) FROM generation_job WHERE story_id = ?", (story_id,)
    )
    (count,) = await cursor.fetchone()
    await conn.close()
    return count


# ── POST /stories/{id}/jobs ───────────────────────────────────────────────────


async def test_post_job_devuelve_202_y_genera_la_historia_completa(client):
    story_id = await _create_story(client)

    resp = await client.post(f"/api/v1/stories/{story_id}/jobs", json={})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    assert resp.json()["status"] == "queued"

    await job_manager.wait(uuid.UUID(job_id))

    job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert job["status"] == "done", job
    assert job["narrative_id"] is not None
    assert (job["stage"], job["total_beats"]) == ("consolidando", 5)
    story = (await client.get(f"/api/v1/stories/{story_id}")).json()
    assert story["status"] == "completed"


async def test_post_job_con_job_activo_devuelve_409_con_el_mismo_job(client, hold):
    story_id = await _create_story(client)
    first = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()

    resp = await client.post(f"/api/v1/stories/{story_id}/jobs", json={})

    assert resp.status_code == 409
    assert resp.json()["job_id"] == first["job_id"]
    hold.set()
    await job_manager.wait(uuid.UUID(first["job_id"]))


async def test_post_job_historia_inexistente_404(client):
    resp = await client.post(f"/api/v1/stories/{uuid.uuid4()}/jobs", json={})

    assert resp.status_code == 404


async def test_post_job_regenerate_voz_todavia_no_soportado(client):
    story_id = await _create_story(client)

    resp = await client.post(f"/api/v1/stories/{story_id}/jobs", json={"kind": "regenerate_voz"})

    assert resp.status_code == 422


# ── GET /jobs/{id} y cancel ───────────────────────────────────────────────────


@pytest.mark.parametrize("job_id", [str(uuid.uuid4()), "no-es-uuid"])
async def test_get_job_inexistente_404(client, job_id):
    assert (await client.get(f"/api/v1/jobs/{job_id}")).status_code == 404


@pytest.mark.usefixtures("hold")
async def test_cancelar_job_en_curso(client):
    story_id = await _create_story(client)
    job_id = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()["job_id"]
    await asyncio.sleep(0.05)

    resp = await client.post(f"/api/v1/jobs/{job_id}/cancel")

    assert resp.status_code == 200
    assert (resp.json()["status"], resp.json()["error"]) == ("failed", CANCELLED_ERROR)
    story = (await client.get(f"/api/v1/stories/{story_id}")).json()
    assert story["status"] == "failed"
    assert (await client.post(f"/api/v1/jobs/{job_id}/cancel")).status_code == 409


# ── GET /jobs/{id}/events ─────────────────────────────────────────────────────


async def test_events_de_job_terminado_hace_replay_completo_con_ids(client):
    story_id = await _create_story(client)
    job_id = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))

    events = _parse_sse((await client.get(f"/api/v1/jobs/{job_id}/events")).text)

    kinds = [e["event"] for e in events]
    assert kinds.count("beat_done") == 5
    assert kinds[-1] == "done"
    assert [int(e["id"]) for e in events] == list(range(1, len(events) + 1))
    stages = [e["data"]["stage"] for e in events if e["event"] == "status"]
    assert stages[:2] == ["analyst", "resolver"] and stages[-1] == "consolidando"


async def test_events_con_last_event_id_no_repite(client):
    story_id = await _create_story(client)
    job_id = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    full = _parse_sse((await client.get(f"/api/v1/jobs/{job_id}/events")).text)
    cut = int(full[-3]["id"])

    resumed = _parse_sse(
        (
            await client.get(f"/api/v1/jobs/{job_id}/events", headers={"Last-Event-ID": str(cut)})
        ).text
    )

    assert [int(e["id"]) for e in resumed] == [int(e["id"]) for e in full[-2:]]


async def test_events_tras_ttl_reproduce_desde_la_db(client):
    story_id = await _create_story(client)
    job_id = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    event_bus.drop(job_channel(job_id))  # simula el TTL vencido

    events = _parse_sse((await client.get(f"/api/v1/jobs/{job_id}/events")).text)

    assert [e["event"] for e in events].count("beat_done") == 5
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["read_only"] is True


async def test_events_de_job_inexistente_404_y_no_crea_nada(client):
    story_id = await _create_story(client)

    resp = await client.get(f"/api/v1/jobs/{uuid.uuid4()}/events")

    assert resp.status_code == 404
    assert await _job_rows(story_id) == 0


# ── /stories/{id}/stream legado sobre JobManager ──────────────────────────────


async def test_stream_legado_genera_via_job_y_despues_queda_de_lectura(client):
    story_id = await _create_story(client)

    events = _parse_sse((await client.get(f"/api/v1/stories/{story_id}/stream")).text)

    assert [e["event"] for e in events].count("beat_done") == 5
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["narrative_id"] is not None
    assert await _job_rows(story_id) == 1

    again = _parse_sse((await client.get(f"/api/v1/stories/{story_id}/stream")).text)
    assert again[-1]["data"]["read_only"] is True
    assert await _job_rows(story_id) == 1  # la historia completa no se regenera


async def test_stream_legado_se_ata_al_job_activo(client, hold):
    story_id = await _create_story(client)
    job_id = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()["job_id"]

    request = asyncio.create_task(client.get(f"/api/v1/stories/{story_id}/stream"))
    await asyncio.sleep(0.1)
    hold.set()
    events = _parse_sse((await request).text)

    assert [e["event"] for e in events] == ["status", "done"]
    assert await _job_rows(story_id) == 1
    await job_manager.wait(uuid.UUID(job_id))


async def test_stream_legado_historia_inexistente_404(client):
    assert (await client.get(f"/api/v1/stories/{uuid.uuid4()}/stream")).status_code == 404
