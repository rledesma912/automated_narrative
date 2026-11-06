"""Adapter de FreeLLMAPI: el gateway local de capas gratuitas, compatible con OpenAI (Spec-740).

El `model` puede ser una cadena con nombre (`auto:narrativa`): el gateway elige y salta de
modelo solo. Quién respondió de verdad viene en la respuesta (`model`, `X-Routed-Via`).
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

import httpx

from src.config import settings
from src.domain import llm_context
from src.domain.exceptions import LLMRefusalError, LLMResponseError, LLMUnavailableError
from src.domain.interfaces import LLMResponse
from src.messages import message

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TOKENS = 4096
_DEFAULT_MAX_WAIT_SECONDS = 120.0
_REQUEST_TIMEOUT = httpx.Timeout(300.0, connect=10.0)
# Margen sobre `retryAtMs`, para no volver justo cuando vence el cooldown.
_WAIT_MARGIN_SECONDS = 1.0
# Si el gateway no dice cuándo vuelve, se prueba de a poco hasta el tope.
_NO_DATE_WAIT_SECONDS = 30.0
# Un cooldown más largo que esto ya no es la cuota por minuto: es la del día (T1.9: ~17 h).
_DAILY_QUOTA_SECONDS = 3600.0

# Sin caché: regenerar un acto tiene que escribir de nuevo, y un acierto no dice quién
# respondió. Sin compresión: el gateway no toca lo que le decimos a la IA (Spec-740 S0).
_FIXED_HEADERS = {"X-FreeLLM-Cache": "off", "X-FreeLLM-Compress": "off"}

_NO_MODELS_CODES = ("quota_exceeded", "no_providers_configured")
# Cómo marca el gateway, en `X-Fallback-Trail`, un modelo que frenó por cuota.
_RATE_LIMITED = "=rate_limited"


def _error_of(response: httpx.Response) -> dict:
    """El objeto `error` del cuerpo; vacío si el cuerpo no lo trae."""
    try:
        body = response.json()
    except ValueError:
        return {}
    error = body.get("error") if isinstance(body, dict) else None
    return error if isinstance(error, dict) else {}


def _cause(status: int, code: str | None, seconds_to_retry: float | None = None) -> str:
    """Causa de un error HTTP, para el mensaje de `LLMUnavailableError`."""
    if code in _NO_MODELS_CODES:
        return "sin_modelos"
    if seconds_to_retry is not None and seconds_to_retry > _DAILY_QUOTA_SECONDS:
        return "sin_cuota_hoy"
    if status in (401, 403):
        return "clave"
    if status == 429 or status >= 500:
        return "saturada"
    return "error"


def _unavailable(cause: str, detail: object) -> LLMUnavailableError:
    logger.error("[FREELLMAPI] %s: %s", cause, detail)
    return LLMUnavailableError(cause, message(f"llm.{cause}"), detail=str(detail))


class FreeLLMAPIAdapter:
    """Config por rol (perfil): `model`, `num_predict` (→ max_tokens), `temperature` y
    `reasoning_effort`.

    Si toda la cadena está en cooldown, el gateway responde 429, casi siempre con `retryAtMs`:
    se espera hasta esa hora (o de a 30 s si no la da), con un tope por llamada (`freellmapi.max_espera_s` del perfil). Después
    falla con el mensaje coloquial, sin caer a otro proveedor (Spec-740 A8 y D3).
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        max_wait_seconds: float | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], float] = time.time,
    ):
        if client is None:
            key = api_key or settings.freellmapi_api_key
            if not key:
                raise ValueError(
                    "FREELLMAPI_API_KEY no configurada. "
                    "Agrégala al .env o exporta la variable de entorno."
                )
            client = httpx.AsyncClient(
                base_url=base_url or settings.freellmapi_url,
                headers={"Authorization": f"Bearer {key}"},
                timeout=_REQUEST_TIMEOUT,
            )
        self._client = client
        block = settings.active_profile_config().get("freellmapi") or {}
        self._max_wait = (
            max_wait_seconds
            if max_wait_seconds is not None
            else float(block.get("max_espera_s", _DEFAULT_MAX_WAIT_SECONDS))
        )
        self._sleep = sleep
        self._now = now

    def _request(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str | None,
        temperature: float | None,
        role: str | None,
        num_predict: int | None,
        response_schema: dict | None,
    ) -> dict:
        role_cfg = settings.role_config(role) if role else {}
        messages = [{"role": "user", "content": prompt}]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})
        request: dict = {
            "model": model or role_cfg.get("model") or "auto",
            "messages": messages,
            "max_tokens": int(num_predict or role_cfg.get("num_predict") or _DEFAULT_MAX_TOKENS),
        }
        temperature = temperature if temperature is not None else role_cfg.get("temperature")
        if temperature is not None:
            request["temperature"] = temperature
        # Spec-740 T1.9: un modelo que razona gasta `max_tokens` sin mostrarlo y se corta
        # (`gemini-3.5-flash`: 64 palabras con 2000 tokens; con `low`, 433 y completo).
        if role_cfg.get("reasoning_effort"):
            request["reasoning_effort"] = role_cfg["reasoning_effort"]
        if response_schema:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.get("title") or "respuesta",
                    "schema": response_schema,
                },
            }
        return request

    @staticmethod
    def _headers() -> dict[str, str]:
        headers = dict(_FIXED_HEADERS)
        context = llm_context.current()
        if context is not None:
            # El mismo modelo durante todo el job, mientras tenga cuota.
            headers["X-Session-Id"] = str(context.job_id)
        return headers

    def _wait_for(self, response: httpx.Response, waited: float) -> float | None:
        """Segundos a esperar antes de reintentar, o None si no hay que hacerlo."""
        if response.status_code == 502 and _RATE_LIMITED in response.headers.get(
            "X-Fallback-Trail", ""
        ):
            # T1.9: un límite por minuto que llega como 502 (falló el modelo limitado y el
            # siguiente por otra causa). Vuelve solo, como un 429 sin hora.
            wait = _NO_DATE_WAIT_SECONDS
            return wait if waited + wait <= self._max_wait else None
        if response.status_code != 429:
            return None
        error = _error_of(response)
        if error.get("code") in _NO_MODELS_CODES:
            return None
        retry_at = error.get("retryAtMs")
        if isinstance(retry_at, int | float):
            wait = max(retry_at / 1000 - self._now(), 0.0) + _WAIT_MARGIN_SECONDS
        else:
            # «Agotado» sin hora de vuelta (T1.9): las cuotas por minuto vuelven solas.
            wait = _NO_DATE_WAIT_SECONDS
        return wait if waited + wait <= self._max_wait else None

    async def _post(self, request: dict) -> tuple[httpx.Response, float]:
        """Manda el pedido, esperando los cooldowns. Devuelve la respuesta y lo esperado."""
        waited = 0.0
        while True:
            try:
                response = await self._client.post(
                    "/v1/chat/completions", json=request, headers=self._headers()
                )
            except httpx.TransportError as e:  # incluye el timeout
                raise _unavailable("sin_conexion", e) from e
            wait = self._wait_for(response, waited)
            if wait is None:
                return response, waited
            logger.warning("[FREELLMAPI] %s en cooldown: espero %.0f s", request["model"], wait)
            await self._sleep(wait)
            waited += wait

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        role: str | None = None,
        num_ctx: int | None = None,  # Ollama; sin efecto acá
        num_predict: int | None = None,
        response_schema: dict | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Genera texto con el gateway."""
        request = self._request(
            prompt, system_prompt, model, temperature, role, num_predict, response_schema
        )
        t0 = time.perf_counter()
        response, waited = await self._post(request)
        elapsed = time.perf_counter() - t0

        if response.status_code != 200:
            error = _error_of(response)
            retry_at = error.get("retryAtMs")
            seconds_to_retry = (
                retry_at / 1000 - self._now() if isinstance(retry_at, int | float) else None
            )
            raise _unavailable(
                _cause(response.status_code, error.get("code"), seconds_to_retry),
                f"{response.status_code} {error.get('code')}: {error.get('message')}",
            )

        try:
            body = response.json()
            choice = body["choices"][0]
            text = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise LLMResponseError(reason="respuesta sin el formato esperado") from e

        finish = choice.get("finish_reason")
        answered_by = body.get("model")
        usage = body.get("usage") or {}
        # En WARNING: la API no muestra INFO y, hasta el registro (Spec-740 S2), este es el
        # único rastro de quién respondió.
        logger.warning(
            "[FREELLMAPI] rol=%s pedido=%s via=%s finish=%s saltos=%s trail=%s esperó=%.0fs "
            "in=%s out=%s elapsed=%.1fs",
            role,
            request["model"],
            response.headers.get("X-Routed-Via"),
            finish,
            response.headers.get("X-Fallback-Attempts"),
            response.headers.get("X-Fallback-Trail"),
            waited,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            elapsed,
        )
        if finish == "content_filter":
            raise LLMRefusalError("content_filter")
        if finish == "length":
            # Un acto truncado no se persiste.
            raise LLMResponseError(
                reason=f"respuesta truncada (max_tokens={request['max_tokens']})"
            )
        if not text.strip():
            raise LLMResponseError(reason="respuesta vacía")

        return LLMResponse(
            text=text,
            elapsed_s=elapsed,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            model=answered_by,
        )

    async def close(self) -> None:
        """Cierra el cliente HTTP."""
        await self._client.aclose()
