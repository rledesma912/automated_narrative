"""FreeLLMAPIAdapter (Spec-740 S1): sin red, con `httpx.MockTransport`."""

import json
import uuid

import httpx
import pytest

from src.domain import llm_context
from src.domain.exceptions import LLMRefusalError, LLMResponseError, LLMUnavailableError
from src.infrastructure.adapters import FreeLLMAPIAdapter
from src.messages import message

NOW = 1_000.0


def ok(text="Texto del acto.", *, finish="stop", model="openai/gpt-oss-120b", headers=None):
    return httpx.Response(
        200,
        json={
            "model": model,
            "choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        },
        headers=headers or {"X-Routed-Via": f"groq/{model}"},
    )


def failure(status, code=None, **extra):
    return httpx.Response(status, json={"error": {"message": "mal", "code": code, **extra}})


class Gateway:
    """Responde en orden lo que se le da y guarda los pedidos."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def adapter(self, **kwargs) -> FreeLLMAPIAdapter:
        async def sleep(seconds: float) -> None:
            self.sleeps.append(seconds)

        client = httpx.AsyncClient(
            base_url="http://gateway.test", transport=httpx.MockTransport(self._handle)
        )
        return FreeLLMAPIAdapter(
            client=client, sleep=sleep, now=lambda: NOW, max_wait_seconds=120, **kwargs
        )

    def body(self, index: int = 0) -> dict:
        return json.loads(self.requests[index].content)


async def test_llamada_feliz():
    gateway = Gateway(ok())
    response = await gateway.adapter().generate(
        "El prompt",
        system_prompt="El sistema",
        model="auto:narrativa",
        temperature=0.7,
        num_predict=2000,
    )

    assert gateway.requests[0].url.path == "/v1/chat/completions"
    assert gateway.body() == {
        "model": "auto:narrativa",
        "messages": [
            {"role": "system", "content": "El sistema"},
            {"role": "user", "content": "El prompt"},
        ],
        "max_tokens": 2000,
        "temperature": 0.7,
    }
    assert response.text == "Texto del acto."
    assert (response.input_tokens, response.output_tokens) == (11, 7)
    assert response.model == "openai/gpt-oss-120b"  # quién respondió, no lo pedido


async def test_sin_cache_ni_compresion_en_cada_pedido():
    gateway = Gateway(ok())
    await gateway.adapter().generate("p", model="auto:narrativa")

    headers = gateway.requests[0].headers
    assert headers["X-FreeLLM-Cache"] == "off"
    assert headers["X-FreeLLM-Compress"] == "off"


async def test_el_esquema_va_como_response_format():
    gateway = Gateway(ok('{"a": 1}'))
    schema = {"title": "Escaleta", "type": "object", "properties": {"a": {"type": "integer"}}}
    await gateway.adapter().generate("p", model="auto:estructura", response_schema=schema)

    assert gateway.body()["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "Escaleta", "schema": schema},
    }


async def test_el_rol_da_modelo_y_tope_si_no_vienen(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(
        type(settings),
        "role_config",
        lambda _self, _role: {"model": "auto:narrativa", "num_predict": 1800, "temperature": 0.5},
    )
    gateway = Gateway(ok())
    await gateway.adapter().generate("p", role="voz")

    body = gateway.body()
    assert (body["model"], body["max_tokens"], body["temperature"]) == (
        "auto:narrativa",
        1800,
        0.5,
    )


async def test_el_rol_pide_poco_razonamiento(monkeypatch):
    """T1.9: si no, un modelo que razona gasta el tope sin mostrarlo y se corta."""
    from src.config import settings

    monkeypatch.setattr(
        type(settings), "role_config", lambda _self, _role: {"reasoning_effort": "low"}
    )
    gateway = Gateway(ok())
    await gateway.adapter().generate("p", role="voz")
    assert gateway.body()["reasoning_effort"] == "low"


async def test_sin_config_no_manda_razonamiento():
    gateway = Gateway(ok())
    await gateway.adapter().generate("p", model="auto")
    assert "reasoning_effort" not in gateway.body()


async def test_sin_job_no_manda_sesion():
    gateway = Gateway(ok())
    await gateway.adapter().generate("p", model="auto")
    assert "X-Session-Id" not in gateway.requests[0].headers


async def test_dentro_de_un_job_la_sesion_es_el_job():
    job_id = uuid.uuid4()
    gateway = Gateway(ok())
    llm_context.enter_job(job_id, uuid.uuid4())
    await gateway.adapter().generate("p", model="auto")
    assert gateway.requests[0].headers["X-Session-Id"] == str(job_id)


@pytest.mark.parametrize(
    ("status", "code", "cause"),
    [
        (401, None, "clave"),
        (403, None, "clave"),
        (429, "quota_exceeded", "sin_modelos"),
        (502, "upstream_failed", "saturada"),
        (503, "no_providers_configured", "sin_modelos"),
        (500, None, "saturada"),
        (413, "context_length_exceeded", "error"),
        (404, "model_not_found", "error"),
        (400, None, "error"),
    ],
)
async def test_cada_error_con_su_causa(status, code, cause):
    gateway = Gateway(failure(status, code))
    with pytest.raises(LLMUnavailableError) as e:
        await gateway.adapter().generate("p", model="auto")

    assert e.value.cause == cause
    assert str(e.value) == message(f"llm.{cause}")
    assert gateway.sleeps == []


async def test_error_con_cuerpo_que_no_es_json():
    gateway = Gateway(httpx.Response(502, text="<html>nginx</html>"))
    with pytest.raises(LLMUnavailableError) as e:
        await gateway.adapter().generate("p", model="auto")
    assert e.value.cause == "saturada"


@pytest.mark.parametrize("error", [httpx.ConnectError("no"), httpx.ReadTimeout("tarde")])
async def test_sin_red(error):
    gateway = Gateway(error)
    with pytest.raises(LLMUnavailableError) as e:
        await gateway.adapter().generate("p", model="auto")
    assert e.value.cause == "sin_conexion"


async def test_filtro_de_contenido_es_un_rechazo():
    gateway = Gateway(ok("", finish="content_filter"))
    with pytest.raises(LLMRefusalError):
        await gateway.adapter().generate("p", model="auto")


async def test_truncada_no_se_persiste():
    gateway = Gateway(ok("A medias", finish="length"))
    with pytest.raises(LLMResponseError, match="truncada"):
        await gateway.adapter().generate("p", model="auto", num_predict=100)


@pytest.mark.parametrize("text", ["", "   \n"])
async def test_vacia_es_un_error(text):
    gateway = Gateway(ok(text))
    with pytest.raises(LLMResponseError, match="vacía"):
        await gateway.adapter().generate("p", model="auto")


async def test_200_con_otra_forma_es_un_error():
    gateway = Gateway(httpx.Response(200, json={"algo": "raro"}))
    with pytest.raises(LLMResponseError, match="formato"):
        await gateway.adapter().generate("p", model="auto")


def cooldown(seconds: float) -> httpx.Response:
    return failure(429, "rate_limit_exceeded", retryAtMs=(NOW + seconds) * 1000)


async def test_espera_el_cooldown_y_responde():
    gateway = Gateway(cooldown(30), ok())
    response = await gateway.adapter().generate("p", model="auto")

    assert response.text == "Texto del acto."
    assert gateway.sleeps == [31.0]  # lo que pide, más el margen
    assert len(gateway.requests) == 2


async def test_varios_cooldowns_seguidos_dentro_del_tope():
    gateway = Gateway(cooldown(30), cooldown(30), ok())
    await gateway.adapter().generate("p", model="auto")
    assert gateway.sleeps == [31.0, 31.0]


async def test_si_pasa_el_tope_no_espera_y_falla():
    gateway = Gateway(cooldown(500))
    with pytest.raises(LLMUnavailableError) as e:
        await gateway.adapter().generate("p", model="auto")

    assert e.value.cause == "saturada"
    assert gateway.sleeps == []


def upstream(trail: str) -> httpx.Response:
    return httpx.Response(
        502,
        json={"error": {"message": "mal", "code": "upstream_failed"}},
        headers={"X-Fallback-Trail": trail},
    )


async def test_un_502_por_cuota_espera_y_reintenta():
    """T1.9: el modelo limitado y el siguiente caído llegan como 502."""
    trail = "google/gemini-3.1-flash-lite key1=rate_limited; groq/qwen key1=model_not_found"
    gateway = Gateway(upstream(trail), ok())
    response = await gateway.adapter().generate("p", model="auto")

    assert response.text == "Texto del acto."
    assert gateway.sleeps == [30.0]


async def test_un_502_sin_cuota_en_el_medio_no_espera():
    gateway = Gateway(upstream("google/gemini-3.5-flash key1=upstream_error"))
    with pytest.raises(LLMUnavailableError) as e:
        await gateway.adapter().generate("p", model="auto")

    assert e.value.cause == "saturada"
    assert gateway.sleeps == []


async def test_un_502_por_cuota_se_rinde_en_el_tope():
    gateway = Gateway(*[upstream("x/y key1=rate_limited") for _ in range(5)])
    with pytest.raises(LLMUnavailableError):
        await gateway.adapter().generate("p", model="auto")
    assert gateway.sleeps == [30.0] * 4


async def test_un_cooldown_de_horas_es_la_cuota_del_dia():
    gateway = Gateway(cooldown(17 * 3600))
    with pytest.raises(LLMUnavailableError) as e:
        await gateway.adapter().generate("p", model="auto")

    assert e.value.cause == "sin_cuota_hoy"
    assert str(e.value) == message("llm.sin_cuota_hoy")
    assert gateway.sleeps == []


async def test_el_tope_es_la_suma_de_las_esperas():
    gateway = Gateway(cooldown(70), cooldown(70))
    with pytest.raises(LLMUnavailableError):
        await gateway.adapter().generate("p", model="auto")
    assert gateway.sleeps == [71.0]


async def test_un_retry_ya_vencido_reintenta_con_el_margen():
    gateway = Gateway(cooldown(-5), ok())
    await gateway.adapter().generate("p", model="auto")
    assert gateway.sleeps == [1.0]


async def test_agotado_sin_hora_prueba_de_a_poco():
    """T1.9: el gateway dice «agotado» sin hora; las cuotas por minuto vuelven solas."""
    gateway = Gateway(failure(429, "rate_limit_exceeded"), ok())
    response = await gateway.adapter().generate("p", model="auto")

    assert response.text == "Texto del acto."
    assert gateway.sleeps == [30.0]


async def test_agotado_sin_hora_se_rinde_en_el_tope():
    gateway = Gateway(*[failure(429, "rate_limit_exceeded") for _ in range(5)])
    with pytest.raises(LLMUnavailableError) as e:
        await gateway.adapter().generate("p", model="auto")

    assert e.value.cause == "saturada"
    assert gateway.sleeps == [30.0] * 4  # 120 s de tope


async def test_cuota_agotada_no_espera_aunque_traiga_hora():
    gateway = Gateway(failure(429, "quota_exceeded", retryAtMs=(NOW + 10) * 1000))
    with pytest.raises(LLMUnavailableError) as e:
        await gateway.adapter().generate("p", model="auto")

    assert e.value.cause == "sin_modelos"
    assert gateway.sleeps == []


async def test_cancelar_durante_la_espera_corta_el_job():
    import asyncio

    gateway = Gateway(cooldown(30))
    client = httpx.AsyncClient(
        base_url="http://gateway.test", transport=httpx.MockTransport(gateway._handle)
    )
    adapter = FreeLLMAPIAdapter(client=client, now=lambda: NOW, max_wait_seconds=120)

    task = asyncio.create_task(adapter.generate("p", model="auto"))
    while not gateway.requests:
        await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(gateway.requests) == 1


def test_sin_clave_no_arranca(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings, "freellmapi_api_key", "")
    with pytest.raises(ValueError, match="FREELLMAPI_API_KEY"):
        FreeLLMAPIAdapter()
