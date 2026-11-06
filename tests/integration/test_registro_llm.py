"""Spec-740 S5 (Parte B): cada llamada a la IA de un job queda anotada con quién respondió.

Sin red: el mock, el Anthropic simulado y `httpx.MockTransport`.
"""

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.domain import llm_context
from src.domain.exceptions import LLMUnavailableError
from src.domain.interfaces import LLMResponse
from src.domain.llm_context import LLMCall
from src.infrastructure.adapters import AnthropicAdapter, MockLLMAdapter, RoleRoutingAdapter
from src.infrastructure.adapters.registro_llm import RegistroLLM
from src.infrastructure.database.connection import get_connection, init_db
from src.infrastructure.database.repositories import SQLLLMCallRepository
from src.infrastructure.factories import LLMFactory
from src.main import app
from src.presentation.runtime import job_manager
from tests.integration.test_job_api import _WIZARD_PAYLOAD
from tests.support.fake_anthropic import FakeAnthropic, message

# ── Cada adapter dice quién respondió ──────────────────────────────────────


async def test_anthropic_informa_su_modelo():
    adapter = AnthropicAdapter(client=FakeAnthropic([message(model="claude-sonnet-5-5")]))
    response = await adapter.generate("p", model="claude-sonnet-5-5")
    assert (response.provider, response.model) == ("anthropic", "claude-sonnet-5-5")


async def test_ollama_informa_su_modelo(monkeypatch):
    from src.infrastructure.adapters import OllamaAdapter

    real = httpx.AsyncClient

    def fake(*args, **kwargs):
        handler = lambda _r: httpx.Response(200, json={"response": "ok", "model": "gemma3:12b"})  # noqa: E731
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake)
    response = await OllamaAdapter().generate("p", model="gemma3:12b")
    assert (response.provider, response.model) == ("ollama", "gemma3:12b")


async def test_freellmapi_informa_la_ruta_y_los_saltos():
    from src.infrastructure.adapters import FreeLLMAPIAdapter

    def handler(_r):
        return httpx.Response(
            200,
            json={
                "model": "qwen/qwen3.8-27b",
                "choices": [{"message": {"content": "Prosa."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
            headers={
                "X-Routed-Via": "groq/qwen/qwen3.8-27b",
                "X-Fallback-Attempts": "1",
                "X-Fallback-Trail": "google/gemini-3.1-flash-lite key1=rate_limited",
            },
        )

    client = httpx.AsyncClient(base_url="http://g", transport=httpx.MockTransport(handler))
    response = await FreeLLMAPIAdapter(client=client).generate("p", model="auto:narrativa")
    assert (response.provider, response.model, response.via) == (
        "freellmapi",
        "qwen/qwen3.8-27b",
        "groq/qwen/qwen3.8-27b",
    )
    assert response.fallback_attempts == 1
    assert "rate_limited" in response.fallback_trail


async def test_el_respaldo_queda_marcado():
    class NoAtiende:
        async def generate(self, prompt, **kwargs):
            raise LLMUnavailableError("saturada", "no")

    routing = RoleRoutingAdapter(
        {"planificador": NoAtiende()},
        default=MockLLMAdapter(),
        respaldo={"planificador": (MockLLMAdapter(), {"model": "gemma3:12b"})},
    )
    response = await routing.generate("p", role="planificador")
    assert response.respaldo is True
    assert routing.respaldos == {"planificador"}


# ── El envoltorio ──────────────────────────────────────────────────────────


class Repo:
    def __init__(self, falla: bool = False):
        self.calls: list[LLMCall] = []
        self.falla = falla

    async def add(self, call):
        if self.falla:
            raise RuntimeError("la base no anda")
        self.calls.append(call)


async def _en_un_job(coro_factory, act=None):
    """Corre la corrutina en una tarea con contexto de job, como JobManager."""
    import asyncio

    job_id, story_id = uuid.uuid4(), uuid.uuid4()

    async def job():
        llm_context.enter_job(job_id, story_id)
        llm_context.set_act(act)
        return await coro_factory()

    return await asyncio.create_task(job()), job_id, story_id


async def test_dentro_de_un_job_anota_la_llamada():
    repo = Repo()
    llm = RegistroLLM(MockLLMAdapter(), repo)
    _, job_id, story_id = await _en_un_job(lambda: llm.generate("p", role="voz"), act=2)

    (call,) = repo.calls
    assert (call.job_id, call.story_id, call.role, call.act) == (job_id, story_id, "voz", 2)
    assert (call.provider, call.model, call.profile) == (
        "mock",
        "mock",
        settings.active_profile_name,
    )


async def test_fuera_de_un_job_solo_delega():
    import asyncio

    repo = Repo()
    llm = RegistroLLM(MockLLMAdapter(), repo)

    async def tarea():
        return await llm.generate("p", role="voz")

    assert (await asyncio.create_task(tarea())).text
    assert repo.calls == []


async def test_si_anotar_falla_la_llamada_sigue():
    llm = RegistroLLM(MockLLMAdapter(), Repo(falla=True))
    response, *_ = await _en_un_job(lambda: llm.generate("p", role="voz"))
    assert response.text  # B4: el relato no se pierde


async def test_los_reintentos_de_json_se_anotan_todos():
    from pydantic import BaseModel

    from src.application.services.authoring.structured_llm import generate_structured
    from src.domain.exceptions import LLMStructuredOutputError

    class Salida(BaseModel):
        a: int

    class Mal:
        async def generate(self, prompt, **kwargs):
            return LLMResponse(text="no es json", provider="mock", model="mock")

    repo = Repo()
    llm = RegistroLLM(Mal(), repo)

    async def pedir():
        with pytest.raises(LLMStructuredOutputError):
            await generate_structured(
                llm, role="planificador", prompt="p", system_prompt="s", output=Salida
            )

    await _en_un_job(pedir)
    assert [c.role for c in repo.calls] == ["planificador", "planificador"]


def test_los_respaldos_se_ven_a_traves_del_envoltorio():
    routing = RoleRoutingAdapter({}, default=MockLLMAdapter())
    routing.respaldos.add("verificador")
    assert RegistroLLM(routing).respaldos == {"verificador"}


# ── De punta a punta, con el mock y la base ────────────────────────────────


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'r.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: RegistroLLM(MockLLMAdapter()))
    )
    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _job(client, story_id: str, body: dict) -> dict:
    resp = await client.post(f"/api/v1/stories/{story_id}/jobs", json=body)
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert job["status"] == "done", job
    return job


async def test_un_relato_deja_una_fila_por_llamada_con_su_acto_y_su_relato(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_WIZARD_PAYLOAD)).json()["id"]
    job = await _job(client, story_id, {})
    narrative_id = uuid.UUID(job["narrative_id"])

    calls = await SQLLLMCallRepository().for_narrative(narrative_id)
    num_actos = job["total_beats"]
    voz = [c.act for c in calls if c.role == "voz"]
    memoria = [c.act for c in calls if c.role == "journal"]
    assert voz == list(range(1, num_actos + 1))
    assert memoria == list(range(1, num_actos + 1))
    assert all(c.job_id == uuid.UUID(job["job_id"]) for c in calls)
    assert all(c.provider == "mock" for c in calls)


async def test_regenerar_un_acto_suma_la_llamada_nueva_de_ese_acto(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_WIZARD_PAYLOAD)).json()["id"]
    narrative_id = (await _job(client, story_id, {}))["narrative_id"]

    regen = await _job(
        client, story_id, {"kind": "regenerate_voz", "beat": 2, "narrative_id": narrative_id}
    )
    calls = await SQLLLMCallRepository().for_narrative(uuid.UUID(narrative_id))
    ultimas = [c for c in calls if c.job_id == uuid.UUID(regen["job_id"])]
    assert sorted((c.role, c.act) for c in ultimas) == [("journal", 2), ("voz", 2)]
    # La última Voz de cada acto: el 2 es la del job nuevo, los demás la del original.
    ultima_voz = {}
    for c in calls:
        if c.role == "voz":
            ultima_voz[c.act] = c.job_id
    assert ultima_voz[2] == uuid.UUID(regen["job_id"])
    assert ultima_voz[1] != uuid.UUID(regen["job_id"])


async def test_borrar_el_relato_o_la_historia_borra_sus_llamadas(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_WIZARD_PAYLOAD)).json()["id"]
    narrative_id = (await _job(client, story_id, {}))["narrative_id"]
    repo = SQLLLMCallRepository()
    assert await repo.for_narrative(uuid.UUID(narrative_id))

    assert (await client.delete(f"/api/v1/generated-narratives/{narrative_id}")).status_code in (
        200,
        204,
    )
    assert await repo.for_narrative(uuid.UUID(narrative_id)) == []

    assert (await client.delete(f"/api/v1/stories/{story_id}")).status_code == 204
    conn = await get_connection()
    try:
        cursor = await conn.execute("SELECT COUNT(*) FROM llm_call WHERE story_id = ?", (story_id,))
        assert (await cursor.fetchone())[0] == 0
    finally:
        await conn.close()


@pytest.mark.usefixtures("client")
async def test_init_db_crea_la_tabla_sobre_una_base_existente():
    await init_db()  # otra vez, sobre la misma base: no rompe
    conn = await get_connection()
    try:
        cursor = await conn.execute("PRAGMA table_info(llm_call)")
        columnas = {row[1] for row in await cursor.fetchall()}
    finally:
        await conn.close()
    assert {"story_id", "job_id", "narrative_id", "profile", "role", "act", "via"} <= columnas


# ── Spec-740 C1: GET /generated-narratives/{id}/ia ─────────────────────────


async def test_la_api_dice_que_ia_escribio_el_relato(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_WIZARD_PAYLOAD)).json()["id"]
    job = await _job(client, story_id, {})
    body = (await client.get(f"/api/v1/generated-narratives/{job['narrative_id']}/ia")).json()

    actos = list(range(1, job["total_beats"] + 1))
    assert body["modelos"] == [{"nombre": "IA de prueba", "actos": actos}]
    assert set(body["por_acto"]) == {str(a) for a in actos}
    assert {"tarea": "La memoria de cada acto", "nombre": "IA de prueba"} in body["resto"]


async def test_un_relato_sin_registro_no_dice_nada(client):
    from src.domain.models import GeneratedNarrative
    from src.infrastructure.database.repositories import SQLGeneratedNarrativeRepository

    story_id = (await client.post("/api/v1/stories?action=save", json=_WIZARD_PAYLOAD)).json()["id"]
    viejo = await SQLGeneratedNarrativeRepository().save(
        GeneratedNarrative(
            story_template_id=uuid.UUID(story_id), title="Viejo", content="## Acto 1\n\nX."
        )
    )
    body = (await client.get(f"/api/v1/generated-narratives/{viejo.id}/ia")).json()
    assert body == {"modelos": [], "por_acto": {}, "resto": []}


async def test_la_ia_de_un_relato_que_no_existe_es_404(client):
    resp = await client.get(f"/api/v1/generated-narratives/{uuid.uuid4()}/ia")
    assert resp.status_code == 404
