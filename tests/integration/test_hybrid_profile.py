"""Spec-480 S2 / Spec-600: perfil híbrido (Voz en Claude Sonnet 5.5, resto en Ollama).

Nada llama a una API real: Ollama es el LLM que graba (tests/support) y Anthropic el
cliente simulado con los tipos del SDK.
"""

import copy
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest
import yaml

import src.config as config
from src.config import _resolve_active_profile, settings
from src.infrastructure.adapters import AnthropicAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.factories import LLMFactory
from src.main import app
from src.presentation.runtime import job_manager
from tests.integration.test_pipeline_prompts_snapshot import STORY
from tests.support.fake_anthropic import FakeAnthropic, message
from tests.support.recording_llm import RecordingLLM

HYBRID = "hibrido-sonnet55"
CORE = yaml.safe_load(
    (Path(__file__).parents[2] / "config" / "llm_core_definitions.yaml").read_text("utf-8")
)


def hybrid_profile() -> dict:
    """La Voz en Claude Sonnet 5.5 y el resto en el modelo local (Spec-600, ruteo Spec-480)."""
    return copy.deepcopy(CORE["profiles"][HYBRID])


@pytest.fixture
def hybrid(monkeypatch):
    """Activa el perfil híbrido solo dentro del test."""
    profile = hybrid_profile()
    monkeypatch.setattr(config, "_profile", profile)
    monkeypatch.setattr(config, "_active_profile_name", HYBRID)
    return profile


# ── T2.1 ─────────────────────────────────────────────────────────────────────


def test_perfiles_el_local_activo_el_hibrido_y_uno_de_claude():
    assert CORE["active_profile"] == "ollama-gemma3-12b"
    assert set(CORE["profiles"]) == {"ollama-gemma3-12b", HYBRID, "anthropic-sonnet55"}
    claude = CORE["profiles"]["anthropic-sonnet55"]
    assert claude["provider"] == "anthropic"
    for role, cfg in claude["roles"].items():
        assert cfg["model"] == "claude-sonnet-5-5", role
        assert "temperature" not in cfg  # Sonnet 5.5 no la acepta
        assert cfg["thinking"] in ("adaptive", "between_tools")  # `disabled` es un 400
    _, resolved = _resolve_active_profile(CORE, env_override="anthropic-sonnet55")
    assert resolved["roles"]["voz"]["model"] == "claude-sonnet-5-5"


def test_el_hibrido_solo_manda_la_voz_y_el_guion_a_claude():
    """Spec-600: los roles locales del híbrido son los de gemma, tal cual.

    Spec-610 (D3): el paquete para el video (`guion`) también va a Claude.
    """
    hybrid = CORE["profiles"][HYBRID]
    local = CORE["profiles"]["ollama-gemma3-12b"]
    assert hybrid["provider"] == "ollama"
    assert hybrid["roles"]["voz"] == {
        "provider": "anthropic",
        "model": "claude-sonnet-5-5",
        "num_predict": 2500,
        "thinking": "adaptive",
        "effort": "low",
    }
    assert hybrid["roles"]["guion"]["provider"] == "anthropic"
    for role, cfg in hybrid["roles"].items():
        if role not in ("voz", "guion"):
            assert cfg == local["roles"][role], role


# ── T2.2 ─────────────────────────────────────────────────────────────────────


@pytest.fixture
async def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'h.db'}")
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_verifica_cada_proveedor_en_uso(client, hybrid, monkeypatch):
    hybrid["ollama"]["host"] = "http://127.0.0.1:9"  # nadie escucha
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")

    checks = (await client.get("/api/v1/health")).json()["checks"]

    assert checks["providers"] == ["anthropic", "ollama"]
    assert checks["anthropic_key"] == "present"
    assert checks["ollama"].startswith("error")


@pytest.mark.usefixtures("hybrid")
async def test_health_sin_key_de_anthropic_es_degradado(client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    body = (await client.get("/api/v1/health")).json()
    assert body["checks"]["anthropic_key"] == "missing"
    assert body["status"] == "degraded"


@pytest.mark.usefixtures("hybrid")
async def test_active_profile_muestra_el_proveedor_de_cada_rol(client):
    body = (await client.get("/api/v1/config/active-profile")).json()
    assert body["active_profile"] == HYBRID
    assert body["roles"]["voz"] == {
        "provider": "anthropic",
        "model": "claude-sonnet-5-5",
        "temperature": None,
    }
    assert body["roles"]["journal"]["provider"] == "ollama"


# ── T2.3 ─────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("hybrid")
async def test_pipeline_completo_la_voz_va_a_claude_y_el_resto_a_ollama(client, monkeypatch):
    local = RecordingLLM()
    fake = FakeAnthropic([message("Prosa de Claude para el acto.", input_tokens=3000)])
    adapters = {"ollama": local, "anthropic": AnthropicAdapter(client=fake)}
    monkeypatch.setattr(LLMFactory, "_single", staticmethod(lambda p: adapters[p]))

    story = copy.deepcopy(STORY)
    resp = await client.post("/api/v1/stories?action=save", json=story)
    job = (await client.post(f"/api/v1/stories/{resp.json()['id']}/jobs", json={})).json()
    await job_manager.wait(uuid.UUID(job["job_id"]))
    done = (await client.get(f"/api/v1/jobs/{job['job_id']}")).json()

    assert done["status"] == "done", done
    # Las 5 llamadas de la Voz fueron a Claude, con el prompt de la escaleta (Spec-530).
    assert len(fake.messages.calls) == 5
    request = fake.messages.calls[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["thinking"] == {"type": "adaptive"}
    assert request["output_config"] == {"effort": "low"}
    assert "temperature" not in request
    assert "OFICIO DE HORROR" in request["system"]
    assert request["messages"][0]["content"].startswith("ACTO 1 DE 5")
    # El resto, al modelo local; ninguna llamada de la Voz ahí.
    assert {c["role"] for c in local.calls} == {"planificador", "verificador", "journal"}
    narrative = (await client.get(f"/api/v1/generated-narratives/{done['narrative_id']}")).json()
    assert narrative["content"].count("Prosa de Claude para el acto.") == 5


@pytest.mark.usefixtures("hybrid")
async def test_sin_credito_el_job_falla_con_un_mensaje_claro(client, monkeypatch):
    """Spec-600 D3: sin caer al modelo local; el texto llega tal cual a `job.error`."""
    local = RecordingLLM()
    fake = FakeAnthropic()
    response = MagicMock(status_code=400)
    fake.messages.create = AsyncMock(
        side_effect=anthropic.BadRequestError(
            message="Your credit balance is too low to access the Anthropic API",
            response=response,
            body={},
        )
    )
    adapters = {"ollama": local, "anthropic": AnthropicAdapter(client=fake)}
    monkeypatch.setattr(LLMFactory, "_single", staticmethod(lambda p: adapters[p]))

    resp = await client.post("/api/v1/stories?action=save", json=copy.deepcopy(STORY))
    job = (await client.post(f"/api/v1/stories/{resp.json()['id']}/jobs", json={})).json()
    await job_manager.wait(uuid.UUID(job["job_id"]))
    failed = (await client.get(f"/api/v1/jobs/{job['job_id']}")).json()

    assert failed["status"] == "failed"
    assert failed["error"].startswith("La IA que escribe el relato se quedó sin crédito.")
    assert "voz" not in {c["role"] for c in local.calls}  # no cayó al modelo local
