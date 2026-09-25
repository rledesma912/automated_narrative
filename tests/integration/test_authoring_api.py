"""Spec-530 S3: API del asistente de autoría (con el LLM simulado)."""

import asyncio
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.factories import LLMFactory
from src.main import app
from src.presentation import authoring_jobs
from src.presentation.runtime import job_manager

API = "/api/v1/authoring"
FORM = {
    "title": "La pena del colectivo",
    "genero": "",
    "subgenero": "",
    "premise": "José ve por el espejo a una mujer que murió en su micro.",
    "effect": "pavor",
    "ending": "Descansa en paz.",
    "ending_intentional": True,
    "telling": "caso",
    "protagonist_name": "José",
    "protagonist_role": "Chofer de micros",
    "narrator": "",
}


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'a.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: MockLLMAdapter())
    )
    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _create(client, **extra) -> dict:
    resp = await client.post(f"{API}/stories", json={**FORM, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _run_job(client, story_id: str, kind: str) -> dict:
    resp = await client.post(f"/api/v1/stories/{story_id}/jobs", json={"kind": kind})
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert job["status"] == "done", job
    return (await client.get(f"{API}/stories/{story_id}")).json()


async def test_opciones(client):
    data = (await client.get(f"{API}/options")).json()
    assert [e["id"] for e in data["effects"]][:2] == ["pavor", "susto"]
    assert data["criteria"][0]["nombre"] == "Qué quiere"


async def test_crear_desde_la_direccion(client):
    state = await _create(client)

    assert state["direction"] == FORM | {"narrator": "José", "effect_other": ""}
    assert state["workshop"]["finish"]["kind"] == "sin_analizar"
    assert state["characters"] == [{"name": "José", "kind": "persona", "relation": ""}]
    story = (await client.get(f"/api/v1/stories/{state['story_id']}")).json()
    assert story["protagonista"] == "José: Chofer de micros"
    assert story["sinopsis"] == FORM["premise"]


async def test_genero_invalido_422(client):
    resp = await client.post(f"{API}/stories", json={**FORM, "genero": "inventado"})
    assert resp.status_code == 422


async def test_guardar_la_direccion_no_toca_el_taller_ni_la_escaleta(client):
    state = await _create(client)
    sid = state["story_id"]
    await _run_job(client, sid, "consult")
    await _run_job(client, sid, "plan_outline")

    resp = await client.put(f"{API}/stories/{sid}/direction", json={**FORM, "title": "Otra"})

    after = resp.json()
    assert resp.status_code == 200
    assert after["direction"]["title"] == "Otra"
    assert len(after["workshop"]["items"]) == 5
    assert len(after["outline"]["acts"]) == 5


async def test_taller_con_la_ia(client):
    sid = (await _create(client))["story_id"]

    state = await _run_job(client, sid, "consult")

    items = {w["criterion"]: w for w in state["workshop"]["items"]}
    assert items["final"]["status"] == "intencional"  # no se evalúa
    assert items["meta"]["question"] == "¿Pregunta de ejemplo sobre meta?"
    assert len(items["meta"]["options"]) == 3
    assert items["meta"]["nombre"] == "Qué quiere" and items["meta"]["por_que"]
    assert state["workshop"]["round"] == 1
    assert state["workshop"]["finish"]["kind"] == "abierto"


async def test_taller_sin_de_que_trata_422(client):
    sid = (await _create(client, premise=""))["story_id"]
    resp = await client.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "consult"})
    assert resp.status_code == 422


async def test_acciones_del_taller(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "consult")

    async def act(criterion, **body):
        resp = await client.patch(f"{API}/stories/{sid}/workshop/{criterion}", json=body)
        return resp

    state = (await act("meta", action="answer", text="Llegar a casa")).json()
    state = (await act("en_juego", action="decide")).json()
    state = (await act("vulnerabilidad", action="intentional", text="Así")).json()
    items = {w["criterion"]: w for w in state["workshop"]["items"]}
    assert (items["meta"]["status"], items["meta"]["answer"], items["meta"]["question"]) == (
        "cumple",
        "Llegar a casa",
        "",
    )
    assert items["en_juego"]["answer"] == "Primera opción (en_juego)"
    assert items["vulnerabilidad"]["status"] == "intencional"
    assert [d["id"] for d in state["outline"]["decisions"]] == [
        "meta",
        "en_juego",
        "vulnerabilidad",
        "final",
    ]

    state = (await act("vulnerabilidad", action="reopen")).json()
    assert (
        next(w for w in state["workshop"]["items"] if w["criterion"] == "vulnerabilidad")["status"]
        == "falta"
    )
    assert (await act("inventado", action="decide")).status_code == 404
    assert (await act("meta", action="answer", text="  ")).status_code == 422


async def test_escaleta_y_revision(client):
    sid = (await _create(client))["story_id"]
    assert (
        await client.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "verify_outline"})
    ).status_code == 422

    state = await _run_job(client, sid, "plan_outline")

    acts = state["outline"]["acts"]
    assert [a["number"] for a in acts] == [1, 2, 3, 4, 5]
    assert acts[1]["warnings"] == ["El encuentro del acto 2 repite el del acto 1."]
    assert "Escenario de ejemplo" in state["scenarios"]
    state = await _run_job(client, sid, "verify_outline")
    assert state["outline"]["acts"][1]["warnings"]


async def test_editar_un_acto(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")

    resp = await client.put(
        f"{API}/stories/{sid}/outline/2",
        json={"goal": "  Huir ", "events": ["Frena", " ", "Baja"], "scenario": "La ruta"},
    )

    act = resp.json()["outline"]["acts"][1]
    assert (act["goal"], act["events"], act["scenario"]) == ("Huir", ["Frena", "Baja"], "La ruta")
    assert act["warnings"]  # quedan hasta revisar de nuevo
    assert (await client.put(f"{API}/stories/{sid}/outline/6", json={})).status_code == 404


async def test_con_la_ia_trabajando_no_se_puede_guardar(client, monkeypatch):
    sid = (await _create(client))["story_id"]
    block = asyncio.Event()

    def _runner(_story_id):
        def _run():
            async def _gen():
                await block.wait()
                yield StreamEvent(event=StreamEventType.DONE, data={})

            return _gen()

        return _run

    monkeypatch.setitem(authoring_jobs._RUNNERS, authoring_jobs.JobKind.CONSULT, _runner)
    job = (await client.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "consult"})).json()

    state = (await client.get(f"{API}/stories/{sid}")).json()
    assert state["active_job"]["kind"] == "consult"
    assert (await client.put(f"{API}/stories/{sid}/direction", json=FORM)).status_code == 409
    resp = await client.patch(f"{API}/stories/{sid}/workshop/meta", json={"action": "decide"})
    assert resp.status_code == 409 and resp.headers["x-job-id"] == job["job_id"]
    block.set()
    await job_manager.wait(uuid.UUID(job["job_id"]))


async def test_estimaciones_de_los_jobs_nuevos(client):
    data = (await client.get("/api/v1/jobs/estimates")).json()
    assert {"consult", "plan_outline", "verify_outline"} <= data.keys()
