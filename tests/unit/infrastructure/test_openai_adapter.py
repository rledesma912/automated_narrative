"""Tests de OpenAIAdapter (Spec-740 Parte F). Nunca llaman a la API: cliente simulado."""

from unittest.mock import patch

import pytest

from src.domain.exceptions import LLMRefusalError, LLMResponseError, LLMUnavailableError
from src.domain.interfaces import LLMResponse
from src.infrastructure.adapters.openai_adapter import (
    OpenAIAdapter,
    drop_added_nulls,
    openai_json_schema,
)
from tests.support.fake_openai import FakeOpenAI, completion, connection_error, status_error


@pytest.fixture(autouse=True)
def role_config(monkeypatch):
    """Config por rol del perfil (sin tocar el YAML real); vacía salvo que el test la cargue."""
    from src.config import settings

    roles: dict = {}
    monkeypatch.setattr(type(settings), "role_config", lambda _self, role: roles.get(role, {}))
    return roles


def _adapter(*responses) -> tuple[OpenAIAdapter, FakeOpenAI]:
    client = FakeOpenAI(list(responses) or None)
    return OpenAIAdapter(client=client, default_model="gpt-4.1"), client


def _sent(client: FakeOpenAI) -> dict:
    return client.chat.completions.calls[0]


# ── Init ─────────────────────────────────────────────────────────────────────


def test_sin_api_key_lanza_valueerror():
    with patch("src.infrastructure.adapters.openai_adapter.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAIAdapter()


def test_el_sdk_sale_sin_reintentos():
    """F3: si no atiende, se avisa enseguida; el SDK no reintenta por su cuenta."""
    with patch("src.infrastructure.adapters.openai_adapter.openai.AsyncOpenAI") as sdk:
        OpenAIAdapter(api_key="clave")
    assert sdk.call_args.kwargs["max_retries"] == 0


# ── El pedido (T8.1) ─────────────────────────────────────────────────────────


async def test_pedido_basico_con_system_y_tope():
    adapter, client = _adapter()
    await adapter.generate("prompt", system_prompt="sistema", num_predict=1500, temperature=0.7)
    sent = _sent(client)
    assert sent["model"] == "gpt-4.1"
    assert sent["messages"] == [
        {"role": "system", "content": "sistema"},
        {"role": "user", "content": "prompt"},
    ]
    assert sent["max_completion_tokens"] == 1500
    assert "max_tokens" not in sent
    assert sent["temperature"] == 0.7


async def test_sin_system_prompt_solo_va_el_usuario():
    adapter, client = _adapter()
    await adapter.generate("prompt")
    assert [m["role"] for m in _sent(client)["messages"]] == ["user"]


@pytest.mark.parametrize("model", ["gpt-5-mini", "gpt-5.1", "o3-mini", "o4-mini"])
async def test_los_que_razonan_no_reciben_temperature_y_tienen_piso(model):
    adapter, client = _adapter()
    await adapter.generate("prompt", model=model, temperature=0.7, num_predict=2000)
    sent = _sent(client)
    assert "temperature" not in sent
    assert sent["max_completion_tokens"] == 16000  # el razonamiento sale del mismo tope


async def test_sin_razonar_no_hay_piso(role_config):
    role_config["voz"] = {"model": "gpt-5-mini", "num_predict": 2000, "reasoning_effort": "none"}
    adapter, client = _adapter()
    await adapter.generate("prompt", role="voz")
    sent = _sent(client)
    assert sent["reasoning_effort"] == "none"
    assert sent["max_completion_tokens"] == 2000
    assert sent["model"] == "gpt-5-mini"


async def test_sin_reasoning_effort_no_se_manda():
    adapter, client = _adapter()
    await adapter.generate("prompt")
    assert "reasoning_effort" not in _sent(client)


async def test_nada_del_gateway_va_en_el_pedido():
    """D9: ni headers ni cadenas de FreeLLMAPI; el pedido es solo lo de OpenAI."""
    adapter, client = _adapter()
    await adapter.generate("prompt", role="voz")
    sent = _sent(client)
    assert set(sent) <= {
        "model",
        "messages",
        "max_completion_tokens",
        "temperature",
        "reasoning_effort",
        "response_format",
    }
    assert not sent["model"].startswith("auto")


# ── La respuesta y los errores (T8.2) ────────────────────────────────────────


async def test_devuelve_texto_tokens_y_modelo_que_respondio():
    adapter, _ = _adapter(completion("Prosa.", input_tokens=10, output_tokens=20))
    response = await adapter.generate("prompt")
    assert isinstance(response, LLMResponse)
    assert response.text == "Prosa."
    assert (response.input_tokens, response.output_tokens) == (10, 20)
    assert response.provider == "openai"
    assert response.model == "gpt-5-mini-2026-01-01"


async def test_refusal_es_error():
    adapter, _ = _adapter(completion(None, refusal="No puedo ayudar con eso."))
    with pytest.raises(LLMRefusalError):
        await adapter.generate("prompt")


async def test_content_filter_es_refusal():
    adapter, _ = _adapter(completion("", finish_reason="content_filter"))
    with pytest.raises(LLMRefusalError):
        await adapter.generate("prompt")


async def test_truncado_es_error():
    adapter, _ = _adapter(completion("Prosa cortada a la mi", finish_reason="length"))
    with pytest.raises(LLMResponseError, match="truncada"):
        await adapter.generate("prompt")


@pytest.mark.parametrize(
    "response", [completion(""), completion(None), completion(without_choices=True)]
)
async def test_vacio_es_error(response):
    adapter, _ = _adapter(response)
    with pytest.raises(LLMResponseError, match="vacía"):
        await adapter.generate("prompt")


@pytest.mark.parametrize(
    ("status", "code", "cause", "match"),
    [
        (429, "insufficient_quota", "credito", "sin crédito"),
        (401, "invalid_api_key", "clave", "no acepta la clave"),
        (403, None, "clave", "no acepta la clave"),
        (429, "rate_limit_exceeded", "saturada", "saturada"),
        (500, None, "saturada", "saturada"),
        (503, None, "saturada", "saturada"),
        (400, "invalid_request_error", "error", "respondió con un error"),
    ],
)
async def test_errores_de_la_api_son_un_mensaje_claro(status, code, cause, match):
    """Spec-600 D3: falla enseguida con un texto que entiende quien escribía el relato."""
    adapter, client = _adapter(status_error(status, code=code))
    with pytest.raises(LLMUnavailableError, match=match) as exc:
        await adapter.generate("prompt")
    assert exc.value.cause == cause
    assert "[OPENAI]" not in str(exc.value)
    assert len(client.chat.completions.calls) == 1  # sin reintentos


async def test_sin_conexion_es_un_mensaje_claro():
    adapter, _ = _adapter(connection_error())
    with pytest.raises(LLMUnavailableError, match="sin conexión") as exc:
        await adapter.generate("prompt")
    assert exc.value.cause == "sin_conexion"


async def test_close_sin_cliente_http_no_falla():
    adapter, _ = _adapter()
    await adapter.close()


# ── Salida estructurada (T8.3) ───────────────────────────────────────────────


SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/$defs/Item"},
        },
        "nota": {"type": "string", "default": ""},
    },
    "required": ["items"],
    "$defs": {
        "Item": {
            "type": "object",
            "properties": {
                "x": {"type": "string", "maxLength": 20},
                "y": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                "z": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["x"],
        }
    },
}


def test_el_esquema_estricto_pide_todo_y_nada_mas():
    strict = openai_json_schema(SCHEMA)
    assert strict["additionalProperties"] is False
    assert strict["required"] == ["items", "nota"]
    assert strict["properties"]["nota"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert "minItems" not in strict["properties"]["items"]
    item = strict["$defs"]["Item"]
    assert item["additionalProperties"] is False
    assert item["required"] == ["x", "y", "z"]
    assert "maxLength" not in item["properties"]["x"]
    assert item["properties"]["y"] == {"anyOf": [{"type": "integer"}, {"type": "null"}]}
    assert "minItems" in SCHEMA["properties"]["items"]  # no muta el de quien llama


def test_los_null_de_relleno_se_sacan_y_los_reales_quedan():
    data = {"items": [{"x": "a", "y": None, "z": None}], "nota": None}
    assert drop_added_nulls(data, SCHEMA) == {"items": [{"x": "a"}]}


async def test_response_format_con_el_esquema_estricto(role_config):
    role_config["consultor"] = {"model": "gpt-5-mini", "num_predict": 1500}
    body = '{"items": [{"x": "a", "y": null, "z": null}], "nota": null}'
    adapter, client = _adapter(completion(body))
    response = await adapter.generate("p", role="consultor", response_schema=SCHEMA)

    fmt = _sent(client)["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["name"] == "consultor"
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False
    assert response.text == '{"items": [{"x": "a"}]}'


async def test_sin_response_schema_no_hay_formato():
    adapter, client = _adapter()
    await adapter.generate("p", role="voz")
    assert "response_format" not in _sent(client)


# ── Los esquemas reales de cada rol (T8.3) ───────────────────────────────────


def _roles():
    from src.application.services.authoring import consultant, revisor
    from src.application.services.authoring.final_de_la_idea import FinalDeLaIdeaSalida
    from src.application.services.authoring.outline_narrator import Memoria
    from src.application.services.authoring.planner import escaleta_model
    from src.application.services.authoring.verifier import Revision
    from src.application.services.video.schema import PaqueteIA

    video = "ACTO 1 Cómo empieza\n[1] Uno.\n[2] Dos.\nACTO 2 Qué pasa\n[1] Tres.\n"
    return [
        ("consultor", consultant._output_model(["meta", "final"]), ""),
        ("consultor", FinalDeLaIdeaSalida, "LA IDEA: Un hombre. Se va.\n\nDevolvé:"),
        ("revisor", revisor._output_model(["meta"]), "Se agregó o se cambió:\n- Algo\n"),
        ("planificador", escaleta_model(3), "1. A (intensidad x)\n3. C (intensidad y)"),
        ("planificador", escaleta_model(5), ""),
        ("verificador", Revision, ""),
        ("journal", Memoria, ""),
        ("guion", PaqueteIA, video),
    ]


def _strict_nodes(node):
    if isinstance(node, dict):
        if "properties" in node:
            yield node
        for v in node.values():
            yield from _strict_nodes(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strict_nodes(v)


def _as_openai_answers(value, node, defs):
    """Lo que manda OpenAI en modo estricto: cada campo que no vino, como `null`."""
    from src.infrastructure.adapters.openai_adapter import _items_schema, _object_schema

    if isinstance(value, dict):
        obj = _object_schema(node, defs) or {}
        props = obj.get("properties", {})
        out = {k: _as_openai_answers(v, props.get(k, {}), defs) for k, v in value.items()}
        return {**{k: None for k in props if k not in out}, **out}
    if isinstance(value, list):
        return [_as_openai_answers(v, _items_schema(node, defs), defs) for v in value]
    return value


@pytest.mark.parametrize(
    ("role", "output", "prompt"), _roles(), ids=lambda x: getattr(x, "__name__", None)
)
def test_cada_rol_pasa_por_el_modo_estricto_y_vuelve_valido(role, output, prompt):
    from src.infrastructure.adapters.mock_structured import mock_structured

    schema = output.model_json_schema()
    strict = openai_json_schema(schema)
    for obj in _strict_nodes(strict):
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])

    answer = _as_openai_answers(
        mock_structured(role, schema, prompt), strict, strict.get("$defs", {})
    )
    output.model_validate(drop_added_nulls(answer, schema))
