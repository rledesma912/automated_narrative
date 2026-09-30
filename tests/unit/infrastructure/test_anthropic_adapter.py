"""Tests para AnthropicAdapter (Spec-480 S1). Nunca llaman a la API: cliente simulado."""

from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from src.domain.exceptions import LLMRefusalError, LLMResponseError, LLMUnavailableError
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


async def test_sonnet55_sin_pensar_es_between_tools(role_config):
    """Spec-600: Sonnet 5.5 rechaza `disabled`; lo más bajo es `between_tools`, sin piso."""
    role_config["voz"] = {
        "model": "claude-sonnet-5-5",
        "num_predict": 2500,
        "thinking": "between_tools",
        "effort": "high",
    }
    adapter, client = _adapter()
    await adapter.generate("contexto", role="voz", temperature=0.6)

    request = client.messages.calls[0]
    assert request["thinking"] == {"type": "between_tools"}
    assert request["max_tokens"] == 2500
    assert request["output_config"] == {"effort": "high"}
    assert "temperature" not in request


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


def _status_error(error, status: int, text: str = "x", body: dict | None = None):
    response = MagicMock(status_code=status)
    return error(message=text, response=response, body=body or {})


@pytest.mark.parametrize(
    ("error", "status", "text", "cause", "match"),
    [
        (anthropic.APIStatusError, 402, "billing", "credito", "sin crédito"),
        (
            anthropic.BadRequestError,
            400,
            "Your credit balance is too low to access the Anthropic API",
            "credito",
            "sin crédito",
        ),
        (anthropic.AuthenticationError, 401, "x", "clave", "no acepta la clave"),
        (anthropic.PermissionDeniedError, 403, "x", "clave", "no acepta la clave"),
        (anthropic.RateLimitError, 429, "x", "saturada", "saturada"),
        (anthropic.InternalServerError, 529, "overloaded", "saturada", "saturada"),
        (anthropic.InternalServerError, 500, "x", "saturada", "saturada"),
        (anthropic.BadRequestError, 400, "campo inválido", "error", "respondió con un error"),
    ],
)
async def test_errores_de_la_api_son_un_mensaje_claro(error, status, text, cause, match):
    """Spec-600 D3: el job falla con un texto que entiende quien generaba el relato."""
    adapter, client = _adapter()
    client.messages.create = AsyncMock(side_effect=_status_error(error, status, text))
    with pytest.raises(LLMUnavailableError, match=match) as exc:
        await adapter.generate("prompt")
    assert exc.value.cause == cause
    assert "[ANTHROPIC]" not in str(exc.value)  # nada técnico en lo que se ve


async def test_sin_conexion_es_un_mensaje_claro():
    adapter, client = _adapter()
    request = MagicMock()
    client.messages.create = AsyncMock(side_effect=anthropic.APIConnectionError(request=request))
    with pytest.raises(LLMUnavailableError, match="sin conexión") as exc:
        await adapter.generate("prompt")
    assert exc.value.cause == "sin_conexion"


async def test_close_sin_cliente_http_no_falla():
    adapter, _ = _adapter()
    await adapter.close()


# ── Spec-530: salida estructurada ────────────────────────────────────────────


async def test_response_schema_va_en_output_config_con_el_effort(role_config):
    role_config["consultor"] = {"model": "claude-sonnet-5", "num_predict": 1500, "effort": "low"}
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {"x": {"type": "string", "maxLength": 20}},
                },
            },
        },
        "required": ["items"],
    }
    adapter, client = _adapter()
    await adapter.generate("p", role="consultor", response_schema=schema)

    fmt = client.messages.calls[0]["output_config"]
    assert fmt["effort"] == "low"
    assert fmt["format"]["type"] == "json_schema"
    sent = fmt["format"]["schema"]
    assert sent["additionalProperties"] is False
    items = sent["properties"]["items"]
    assert "minItems" not in items
    assert items["items"]["additionalProperties"] is False
    assert "maxLength" not in items["items"]["properties"]["x"]
    assert "minItems" in schema["properties"]["items"]  # no muta el esquema de quien llama


async def test_sin_response_schema_no_hay_format(role_config):
    role_config["voz"] = {"model": "claude-sonnet-5", "num_predict": 1500, "thinking": "disabled"}
    adapter, client = _adapter()
    await adapter.generate("p", role="voz")
    assert "output_config" not in client.messages.calls[0]
