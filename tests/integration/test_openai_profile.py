"""Spec-740 Parte F (T8.4): un perfil con OpenAI, la factory, /health y «Lo escribió…».

Sin llamadas reales: la API se simula con `httpx.MockTransport`. El perfil es de prueba;
el de verdad se arma en T8.6, con el modelo elegido.
"""

import httpx
import pytest

import src.config as config
from src.application.services.ia_del_relato import nombre_del_modelo
from src.config import settings
from src.infrastructure.adapters import OllamaAdapter, OpenAIAdapter, RoleRoutingAdapter
from src.infrastructure.adapters.registro_llm import RegistroLLM
from src.infrastructure.factories import LLMFactory
from src.main import app

PERFIL = {
    "provider": "openai",
    "openai": {"model": "gpt-5-mini"},
    "roles": {
        "voz": {"model": "gpt-5-mini", "num_predict": 2000, "reasoning_effort": "low"},
        "planificador": {"model": "gpt-5-mini", "num_predict": 4000},
    },
}


@pytest.fixture
def perfil(monkeypatch):
    monkeypatch.setattr(config, "_profile", PERFIL)
    monkeypatch.setattr(config, "_active_profile_name", "openai-prueba")
    monkeypatch.setattr(settings, "openai_api_key", "clave-de-prueba")
    for structure in ("LARGO", "CORTO"):
        monkeypatch.delenv(f"LLM_PROFILE_{structure}", raising=False)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _api(monkeypatch, handler):
    """Hace que `/health` hable con una API simulada."""
    real = httpx.AsyncClient

    def fake(*args, **kwargs):
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake)


@pytest.mark.usefixtures("perfil")
def test_la_factory_arma_el_adapter_envuelto_en_el_registro():
    llm = LLMFactory.get_provider()
    assert isinstance(llm, RegistroLLM)
    assert isinstance(llm.inner, OpenAIAdapter)
    assert llm.inner.default_model == "gpt-5-mini"


@pytest.mark.usefixtures("perfil")
def test_en_un_perfil_mixto_rutea_por_rol(monkeypatch):
    mixto = {**PERFIL, "roles": {**PERFIL["roles"], "journal": {"provider": "ollama"}}}
    monkeypatch.setattr(config, "_profile", mixto)

    llm = LLMFactory.get_provider().inner

    assert isinstance(llm, RoleRoutingAdapter)
    assert isinstance(llm.adapter_for("voz"), OpenAIAdapter)
    assert isinstance(llm.adapter_for("journal"), OllamaAdapter)


@pytest.mark.usefixtures("perfil")
async def test_health_con_la_clave_aceptada(monkeypatch, client):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    _api(monkeypatch, handler)
    body = (await client.get("/api/v1/health")).json()

    assert body["checks"]["providers"] == ["openai"]
    assert body["checks"]["openai"] == "ok"
    assert body["status"] == "healthy"
    assert seen[0].method == "GET"
    assert seen[0].url == "https://api.openai.com/v1/models"  # no gasta
    assert seen[0].headers["Authorization"] == "Bearer clave-de-prueba"


@pytest.mark.usefixtures("perfil")
async def test_health_con_la_clave_rechazada(monkeypatch, client):
    _api(monkeypatch, lambda _request: httpx.Response(401, json={}))
    body = (await client.get("/api/v1/health")).json()

    assert body["checks"]["openai"] == "http 401"
    assert body["status"] == "degraded"


@pytest.mark.usefixtures("perfil")
async def test_health_sin_red(monkeypatch, client):
    def handler(_request):
        raise httpx.ConnectError("no")

    _api(monkeypatch, handler)
    body = (await client.get("/api/v1/health")).json()

    assert body["checks"]["openai"] == "error: ConnectError"
    assert body["status"] == "degraded"


@pytest.mark.usefixtures("perfil")
async def test_health_sin_clave(monkeypatch, client):
    monkeypatch.setattr(settings, "openai_api_key", "")
    body = (await client.get("/api/v1/health")).json()

    assert body["checks"]["openai"] == "missing key"
    assert body["status"] == "degraded"


@pytest.mark.parametrize(
    ("model", "nombre"),
    [
        ("gpt-5-mini-2026-01-01", "GPT-5 mini"),
        ("gpt-5-nano", "GPT-5 nano"),
        ("gpt-oss-120b", "GPT-OSS 120B"),
        ("gpt-9-turbo", "gpt-9-turbo"),  # uno que no está: su id
    ],
)
def test_el_nombre_que_ven_las_chicas(model, nombre):
    assert nombre_del_modelo(model) == nombre
