"""Tests para AnthropicAdapter (Spec-480 S1). Nunca llaman a la API: cliente simulado."""

from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from src.domain.exceptions import LLMRefusalError, LLMResponseError
from src.domain.interfaces import LLMResponse
from src.infrastructure.adapters.anthropic_adapter import AnthropicAdapter
from tests.support.fake_anthropic import FakeAnthropic, message


class TestAnthropicAdapterInit:
    def test_sin_api_key_lanza_valueerror(self):
        with patch("src.infrastructure.adapters.anthropic_adapter.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            mock_settings.anthropic_model = "claude-sonnet-5"
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                AnthropicAdapter()

    def test_con_api_key_parametro_no_lanza(self):
        from src.config import settings

        with patch("src.infrastructure.adapters.anthropic_adapter.anthropic.AsyncAnthropic"):
            adapter = AnthropicAdapter(api_key="test-key")
            assert adapter.default_model == settings.anthropic_model

    def test_default_model_override(self):
        adapter = AnthropicAdapter(client=FakeAnthropic(), default_model="claude-haiku-4-5")
        assert adapter.default_model == "claude-haiku-4-5"


@pytest.fixture(autouse=True)
def role_config(monkeypatch):
    """Config por rol del perfil (sin tocar el YAML real); vacía salvo que el test la cargue."""
    from src.config import settings

    roles: dict = {}
    monkeypatch.setattr(type(settings), "role_config", lambda _self, role: roles.get(role, {}))
    return roles


def _adapter(*responses) -> tuple[AnthropicAdapter, FakeAnthropic]:
    client = FakeAnthropic(list(responses) or None)
    return AnthropicAdapter(client=client, default_model="claude-sonnet-5"), client


# ── Request (T1.2) ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "model", ["claude-sonnet-5", "claude-opus-5", "claude-opus-4-7", "claude-fable-5-1"]
)
async def test_modelos_sin_sampling_no_reciben_temperature(model):
    adapter, client = _adapter()
    await adapter.generate("prompt", model=model, temperature=0.6)
    assert "temperature" not in client.messages.calls[0]


async def test_modelos_con_sampling_si():
    adapter, client = _adapter()
    await adapter.generate("prompt", model="claude-haiku-4-5", temperature=0.5)
    assert client.messages.calls[0]["temperature"] == 0.5


async def test_voz_con_pensamiento_adaptativo_y_effort(role_config):
    role_config["voz"] = {
        "model": "claude-sonnet-5",
        "num_predict": 1500,
        "thinking": "adaptive",
        "effort": "medium",
    }
    adapter, client = _adapter()
    await adapter.generate("contexto", system_prompt="Sos Irene…", role="voz", temperature=0.6)

    request = client.messages.calls[0]
    assert request["model"] == "claude-sonnet-5"
    assert request["thinking"] == {"type": "adaptive"}
    assert request["output_config"] == {"effort": "medium"}
    assert request["max_tokens"] == 16000  # piso con pensamiento: no trunca el acto
    assert request["system"] == "Sos Irene…"
    assert request["messages"] == [{"role": "user", "content": "contexto"}]
    assert "temperature" not in request


async def test_sin_pensamiento_se_manda_disabled_explicito(role_config):
    """En Sonnet 5 omitir `thinking` corre adaptativo: «sin pensamiento» es explícito."""
    role_config["voz"] = {"model": "claude-sonnet-5", "num_predict": 1500, "thinking": "disabled"}
    adapter, client = _adapter()
    await adapter.generate("contexto", role="voz")

    request = client.messages.calls[0]
    assert request["thinking"] == {"type": "disabled"}
    assert request["max_tokens"] == 1500
    assert "output_config" not in request


async def test_sin_thinking_configurado_no_se_manda_pero_se_reserva_lugar(role_config):
    role_config["voz"] = {"model": "claude-sonnet-5", "num_predict": 1500}
    adapter, client = _adapter()
    await adapter.generate("contexto", role="voz")

    request = client.messages.calls[0]
    assert "thinking" not in request
    assert request["max_tokens"] == 16000


async def test_sin_system_prompt_no_incluye_system():
    adapter, client = _adapter()
    await adapter.generate("prompt")
    assert "system" not in client.messages.calls[0]


# ── Respuesta (T1.3) ─────────────────────────────────────────────────────────


async def test_texto_de_los_bloques_text_aunque_primero_venga_el_pensamiento():
    adapter, _ = _adapter(message("Era una noche oscura.", thinking="Planifico el acto…"))
    result = await adapter.generate("prompt")

    assert isinstance(result, LLMResponse)
    assert result.text == "Era una noche oscura."
    assert isinstance(result.elapsed_s, float)


async def test_informa_el_uso_de_tokens():
    adapter, _ = _adapter(message("texto", input_tokens=3200, output_tokens=950))
    result = await adapter.generate("prompt")
    assert (result.input_tokens, result.output_tokens) == (3200, 950)


async def test_refusal_es_error_con_categoria():
    adapter, _ = _adapter(message("", stop_reason="refusal", refusal_category="cyber"))
    with pytest.raises(LLMRefusalError, match="cyber") as exc:
        await adapter.generate("prompt")
    assert exc.value.category == "cyber"


async def test_acto_truncado_es_error():
    adapter, _ = _adapter(message("La mitad de un ac", stop_reason="max_tokens"))
    with pytest.raises(LLMResponseError, match="truncada"):
        await adapter.generate("prompt")


@pytest.mark.parametrize(
    ("error", "match"),
    [
        (anthropic.AuthenticationError, "API key inválida"),
        (anthropic.RateLimitError, "Rate limit"),
        (anthropic.InternalServerError, "Error 500"),
    ],
)
async def test_errores_de_la_api(error, match):
    adapter, client = _adapter()
    response = MagicMock(status_code=500 if error is anthropic.InternalServerError else 400)
    client.messages.create = AsyncMock(side_effect=error(message="x", response=response, body={}))
    with pytest.raises(RuntimeError, match=match):
        await adapter.generate("prompt")


async def test_close_sin_cliente_http_no_falla():
    adapter, _ = _adapter()
    await adapter.close()
