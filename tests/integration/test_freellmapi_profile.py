"""Spec-740 S1: el perfil `freellmapi-libre`, la factory, /health y los filtros por modelo.

Sin llamadas reales: el gateway se simula con `httpx.MockTransport`.
"""

import copy
from pathlib import Path

import httpx
import pytest
import yaml

import src.config as config
from src.config import LLM_ROLES, _resolve_active_profile, settings
from src.domain.interfaces import LLMResponse
from src.domain.models import ActText
from src.infrastructure.adapters import FreeLLMAPIAdapter, OllamaAdapter, RoleRoutingAdapter
from src.infrastructure.factories import LLMFactory
from src.infrastructure.normalizers import ResponseNormalizer
from src.main import app

PROFILE = "freellmapi-libre"
CORE = yaml.safe_load(
    (Path(__file__).parents[2] / "config" / "llm_core_definitions.yaml").read_text("utf-8")
)


@pytest.fixture
def perfil(monkeypatch):
    monkeypatch.setattr(config, "_profile", copy.deepcopy(CORE["profiles"][PROFILE]))
    monkeypatch.setattr(config, "_active_profile_name", PROFILE)
    monkeypatch.setattr(settings, "freellmapi_api_key", "clave-de-prueba")


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _gateway(monkeypatch, handler):
    """Hace que `/health` hable con un gateway simulado."""
    real = httpx.AsyncClient

    def fake(*args, **kwargs):
        return real(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake)


def test_el_perfil_carga_con_todos_sus_roles():
    name, profile = _resolve_active_profile(CORE, env_override=PROFILE)

    assert name == PROFILE
    assert profile["provider"] == "freellmapi"
    assert set(LLM_ROLES) <= set(profile["roles"])
    assert profile["roles"]["voz"]["model"] == "auto:narrativa"
    # Lo que devuelve JSON nunca va a la cadena de la prosa.
    others = {r: c["model"] for r, c in profile["roles"].items() if r != "voz"}
    assert set(others.values()) == {"auto:estructura"}
    assert all(c["num_predict"] for c in profile["roles"].values())
    assert all(not c.get("respaldo") for c in profile["roles"].values())  # D3


@pytest.mark.usefixtures("perfil")
def test_la_factory_devuelve_el_adapter():
    assert isinstance(LLMFactory.get_provider(), FreeLLMAPIAdapter)


@pytest.mark.usefixtures("perfil")
def test_en_un_perfil_mixto_la_factory_rutea_por_rol(monkeypatch):
    profile = copy.deepcopy(CORE["profiles"][PROFILE])
    profile["roles"]["journal"] = {"provider": "ollama", "model": "gemma3:12b"}
    monkeypatch.setattr(config, "_profile", profile)

    llm = LLMFactory.get_provider()

    assert isinstance(llm, RoleRoutingAdapter)
    assert isinstance(llm.adapter_for("voz"), FreeLLMAPIAdapter)
    assert isinstance(llm.adapter_for("journal"), OllamaAdapter)


@pytest.mark.usefixtures("perfil")
def test_el_perfil_da_el_tope_de_espera(monkeypatch):
    profile = copy.deepcopy(CORE["profiles"][PROFILE])
    profile["freellmapi"]["max_espera_s"] = 45
    monkeypatch.setattr(config, "_profile", profile)
    assert FreeLLMAPIAdapter()._max_wait == 45


@pytest.mark.usefixtures("perfil")
async def test_health_con_el_gateway_arriba(monkeypatch, client):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    _gateway(monkeypatch, handler)
    body = (await client.get("/api/v1/health")).json()

    assert body["checks"]["freellmapi"] == "ok"
    assert body["status"] == "healthy"
    assert seen[0].url.path == "/v1/models"  # no gasta cuota
    assert seen[0].headers["Authorization"] == "Bearer clave-de-prueba"


@pytest.mark.usefixtures("perfil")
async def test_health_con_el_gateway_abajo(monkeypatch, client):
    def handler(_request):
        raise httpx.ConnectError("no")

    _gateway(monkeypatch, handler)
    body = (await client.get("/api/v1/health")).json()

    assert body["checks"]["freellmapi"] == "error: ConnectError"
    assert body["status"] == "degraded"


@pytest.mark.usefixtures("perfil")
async def test_health_con_la_clave_rechazada(monkeypatch, client):
    _gateway(monkeypatch, lambda _request: httpx.Response(401, json={}))
    body = (await client.get("/api/v1/health")).json()

    assert body["checks"]["freellmapi"] == "http 401"
    assert body["status"] == "degraded"


@pytest.mark.usefixtures("perfil")
async def test_health_sin_clave(monkeypatch, client):
    monkeypatch.setattr(settings, "freellmapi_api_key", "")
    body = (await client.get("/api/v1/health")).json()

    assert body["checks"]["freellmapi"] == "missing key"
    assert body["status"] == "degraded"


@pytest.mark.usefixtures("perfil")
async def test_el_filtro_va_por_el_modelo_que_respondio():
    """A5: con `auto:narrativa` pedido, el override es del modelo que respondió."""
    from src.application.use_cases.voz_use_case import VozUseCase

    normalizer = ResponseNormalizer(
        config={
            "strip_line_patterns": [],
            "model_overrides": {"qwen": {"strip_line_patterns_extra": ["^RUIDO DE QWEN$"]}},
        }
    )

    class Llm:
        async def generate(self, prompt, **kwargs):
            return LLMResponse(text="Una línea.\nRUIDO DE QWEN\nOtra línea.", model="qwen/qwen3")

    beat, _ = await VozUseCase(Llm(), normalizer=normalizer).narrate_with_prompts(
        ActText(number=1), "s", "p"
    )
    assert "RUIDO" not in beat.generated_act
    assert "Otra línea." in beat.generated_act
