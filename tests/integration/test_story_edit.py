"""Editar historias ya generadas (Spec-440 §8, S0).

Editar los datos de una historia completada no debe borrar lo generado
(actos, journal, anclas, relatos, jobs) ni cambiar su estado.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter
from src.infrastructure.database.connection import get_connection, init_db
from src.infrastructure.factories import LLMFactory
from src.main import app
from src.presentation import generation
from src.presentation.runtime import job_manager

_ACTOS = {f"act_{n}": {"type": "t", "text": f"Acto {n}: algo pasa."} for n in range(1, 6)}

_PAYLOAD = {
    "title": "Historia original",
    "protagonista": "José: conductor [observador]",
    "relator": "Primera persona en pasado. Narrador: José.",
    "escenarios": "El micro: moderno",
    "sinopsis": "\n\n".join(f"Acto {n}: algo pasa." for n in range(1, 6)),
    "reglas": ["El micro trae casos paranormales"],
    "storyteller_config": {
        "storyteller_id": "P1",
        "atmosphere": {"genre": "folk_horror", "subgenre": "rural", "tone": "constante"},
        "scenarios": [{"name": "El micro", "description": "moderno"}],
        "rules": [{"id": "R1", "text": "El micro trae casos paranormales", "type": "entorno"}],
        "actos": _ACTOS,
        "perception": {"reliability": "poco_confiable"},
    },
    "personajes_full": [{"id": "P1", "name": "José", "role": "conductor", "traits": []}],
}


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'edit.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: MockLLMAdapter())
    )
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _generated_story(client: httpx.AsyncClient) -> str:
    story_id = (await client.post("/api/v1/stories?action=save", json=_PAYLOAD)).json()["id"]
    job_id = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    return story_id


async def _counts(story_id: str) -> dict[str, int]:
    conn = await get_connection()
    out = {}
    for table, col in (
        ("macro_beat", "story_id"),
        ("narrative_journal", "story_id"),
        ("generated_narrative", "story_template_id"),
        ("generation_job", "story_id"),
    ):
        cursor = await conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (story_id,))
        (out[table],) = await cursor.fetchone()
    cursor = await conn.execute(
        "SELECT COUNT(*) FROM macro_beat WHERE story_id = ? AND generated_act != ''", (story_id,)
    )
    (out["actos_narrados"],) = await cursor.fetchone()
    await conn.close()
    return out


async def test_editar_historia_generada_conserva_todo_lo_generado(client):
    story_id = await _generated_story(client)
    before = await _counts(story_id)
    assert before["actos_narrados"] == 5 and before["generated_narrative"] == 1

    edited = {**_PAYLOAD, "title": "Historia editada", "reglas": ["Regla nueva"]}
    edited["storyteller_config"] = {
        **_PAYLOAD["storyteller_config"],
        "rules": [{"id": "R1", "text": "Regla nueva", "type": "psicologica"}],
    }
    resp = await client.patch(f"/api/v1/stories/{story_id}", json=edited)

    assert resp.status_code == 200, resp.text
    assert await _counts(story_id) == before
    story = (await client.get(f"/api/v1/stories/{story_id}")).json()
    assert story["title"] == "Historia editada"
    assert story["status"] == "completed"  # editar no cambia el estado
    conn = await get_connection()
    cursor = await conn.execute("SELECT content, type FROM rule WHERE story_id = ?", (story_id,))
    rules = [tuple(r) for r in await cursor.fetchall()]
    await conn.close()
    assert rules == [("Regla nueva", "psicologica")]


async def test_editar_historia_fallida(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_PAYLOAD)).json()["id"]
    await client.patch(f"/api/v1/stories/{story_id}/status", json={"status": "failed"})

    resp = await client.patch(
        f"/api/v1/stories/{story_id}", json={**_PAYLOAD, "title": "Reintento"}
    )

    assert resp.status_code == 200
    assert (await client.get(f"/api/v1/stories/{story_id}")).json()["title"] == "Reintento"


async def test_editar_con_job_activo_devuelve_409(client, monkeypatch):
    story_id = (await client.post("/api/v1/stories?action=save", json=_PAYLOAD)).json()["id"]
    block = asyncio.Event()

    def _runner(_story):
        async def _gen() -> AsyncIterator[StreamEvent]:
            await block.wait()
            yield StreamEvent(event=StreamEventType.DONE, data={})

        return _gen

    monkeypatch.setattr(generation, "full_generation_runner", _runner)
    job_id = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()["job_id"]

    resp = await client.patch(f"/api/v1/stories/{story_id}", json={**_PAYLOAD, "title": "X"})

    assert resp.status_code == 409
    assert resp.json()["job_id"] == job_id
    block.set()
    await job_manager.wait(uuid.UUID(job_id))


async def test_editar_historia_inexistente_404(client):
    resp = await client.patch(f"/api/v1/stories/{uuid.uuid4()}", json=_PAYLOAD)

    assert resp.status_code == 404


def test_payload_de_prueba_es_json_valido():
    assert json.loads(json.dumps(_PAYLOAD))["title"] == "Historia original"


# ── Vista de autoría para rehidratar el wizard (Spec-440 §8) ──────────────────


def _assert_authoring(sc: dict) -> None:
    assert sc["atmosphere"] == {"genre": "folk_horror", "subgenre": "rural", "tone": "constante"}
    assert [(x["name"], x["description"]) for x in sc["scenarios"]] == [("El micro", "moderno")]
    assert [(r["text"], r["type"]) for r in sc["rules"]] == [
        ("El micro trae casos paranormales", "entorno")
    ]
    assert [sc["actos"][f"act_{n}"]["text"] for n in range(1, 6)] == [
        f"Acto {n}: algo pasa." for n in range(1, 6)
    ]
    assert sc["perception"]["reliability"] == "poco_confiable"


async def test_get_devuelve_la_vista_de_autoria_completa(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_PAYLOAD)).json()["id"]

    story = (await client.get(f"/api/v1/stories/{story_id}")).json()

    _assert_authoring(story["storyteller_config"])


async def test_la_vista_de_autoria_sobrevive_a_una_generacion(client):
    """Tras generar, los actos solo quedan en la sinopsis: igual se reconstruyen."""
    story_id = await _generated_story(client)

    story = (await client.get(f"/api/v1/stories/{story_id}")).json()

    _assert_authoring(story["storyteller_config"])


async def _rule_types(story_id: str) -> dict[str, str | None]:
    conn = await get_connection()
    cursor = await conn.execute("SELECT content, type FROM rule WHERE story_id = ?", (story_id,))
    rows = await cursor.fetchall()
    await conn.close()
    return {content: type_ for content, type_ in rows}


async def test_tipos_de_regla_viejos_se_guardan_mapeados(client):
    """Spec-440 §9: social → entorno, paranormal → fenomeno, evento → sin tipo."""
    payload = json.loads(json.dumps(_PAYLOAD))
    payload["storyteller_config"]["rules"] = [
        {"id": "R1", "text": "Regla social", "type": "social"},
        {"id": "R2", "text": "Regla paranormal", "type": "paranormal"},
        {"id": "R3", "text": "Regla evento", "type": "evento"},
    ]
    story_id = (await client.post("/api/v1/stories?action=save", json=payload)).json()["id"]

    assert await _rule_types(story_id) == {
        "Regla social": "entorno",
        "Regla paranormal": "fenomeno",
        "Regla evento": None,
    }
