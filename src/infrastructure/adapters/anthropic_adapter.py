"""Anthropic API adapter (Spec-480; Spec-600: Claude Sonnet 5.5 en la Voz)."""

import logging
import time

import anthropic

from src.config import settings
from src.domain.exceptions import LLMRefusalError, LLMResponseError, LLMUnavailableError
from src.domain.interfaces import LLMResponse
from src.messages import message

logger = logging.getLogger(__name__)

# Modelos que rechazan los parámetros de sampling (temperature, top_p, top_k) con un 400.
_NO_SAMPLING_PREFIXES = (
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable",
    "claude-mythos",
)
# Con pensamiento, el razonamiento sale del mismo max_tokens: piso para no truncar el texto.
_THINKING_MIN_MAX_TOKENS = 16000
_DEFAULT_MAX_TOKENS = 4096
# Modos de `thinking` que se mandan tal cual. `disabled` lo rechaza Sonnet 5.5 (400): ahí
# lo más bajo es `between_tools` (sin pensamiento extendido, effort `high` o menos).
_THINKING_MODES = ("adaptive", "disabled", "between_tools")
_NO_THINKING = ("disabled", "between_tools")

# Spec-600 D3: lo que ve quien generaba el relato cuando la API no atiende está en
# config/core_messages.yaml (`llm.<causa>`, Spec-620).


# Restricciones de JSON Schema que los structured outputs de Anthropic no aceptan.
_UNSUPPORTED_SCHEMA_KEYS = (
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "multipleOf",
)


def anthropic_json_schema(schema: dict) -> dict:
    """Adapta un JSON Schema a los structured outputs de Anthropic (Spec-530).

    Exigen `additionalProperties: false` en cada objeto y no aceptan restricciones
    numéricas, de largo ni de cantidad de ítems: se quitan (quien llama valida igual).
    """
    if isinstance(schema, list):
        return [anthropic_json_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out = {
        k: anthropic_json_schema(v) for k, v in schema.items() if k not in _UNSUPPORTED_SCHEMA_KEYS
    }
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


def _status_cause(e: anthropic.APIStatusError) -> str:
    """Causa de un error HTTP de la API, para el mensaje de `LLMUnavailableError`."""
    text = str(e).lower()
    if e.status_code == 402 or getattr(e, "type", None) == "billing_error" or "credit" in text:
        # Sin saldo: 402 `billing_error`, o 400 «credit balance is too low».
        return "credito"
    if e.status_code in (401, 403):
        return "clave"
    if e.status_code in (429, 529) or e.status_code >= 500:
        return "saturada"
    return "error"


def _unavailable(cause: str, e: Exception) -> LLMUnavailableError:
    logger.error(f"[ANTHROPIC] {cause}: {e}")
    return LLMUnavailableError(cause, message(f"llm.{cause}"), detail=str(e))


class AnthropicAdapter:
    """Adapter para la API de Anthropic.

    Config por rol (perfil): `model`, `num_predict` (→ max_tokens), `temperature` (solo
    modelos con sampling), `thinking` (`adaptive` | `disabled` | `between_tools`; sin valor
    no se manda y el modelo usa su default — en Sonnet 5 / 5.5 y Opus 5 eso es pensar) y
    `effort`. Sonnet 5.5 rechaza `disabled`: su modo sin pensar es `between_tools`.
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        client: anthropic.AsyncAnthropic | None = None,
    ):
        if client is None:
            key = api_key or settings.anthropic_api_key
            if not key:
                raise ValueError(
                    "ANTHROPIC_API_KEY no configurada. "
                    "Agrégala al .env o exporta la variable de entorno."
                )
            client = anthropic.AsyncAnthropic(api_key=key)
        self._client = client
        self.default_model = default_model or settings.anthropic_model

    def _request(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str | None,
        temperature: float | None,
        role: str | None,
        num_predict: int | None,
        response_schema: dict | None = None,
    ) -> dict:
        role_cfg = settings.role_config(role) if role else {}
        model_name = model or role_cfg.get("model") or self.default_model
        thinking = role_cfg.get("thinking")

        max_tokens = int(num_predict or role_cfg.get("num_predict") or _DEFAULT_MAX_TOKENS)
        if thinking not in _NO_THINKING:
            # Adaptativo explícito, o el default de los modelos que piensan por defecto.
            max_tokens = max(max_tokens, _THINKING_MIN_MAX_TOKENS)

        request: dict = {
            "model": model_name,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            request["system"] = system_prompt
        if thinking in _THINKING_MODES:
            request["thinking"] = {"type": thinking}
        output_config: dict = {}
        if role_cfg.get("effort"):
            output_config["effort"] = role_cfg["effort"]
        if response_schema:
            # Spec-530: JSON outputs (structured outputs); compatible con thinking.
            output_config["format"] = {
                "type": "json_schema",
                "schema": anthropic_json_schema(response_schema),
            }
        if output_config:
            request["output_config"] = output_config
        if temperature is not None and not model_name.startswith(_NO_SAMPLING_PREFIXES):
            request["temperature"] = temperature
        return request

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
        """Genera texto con la API de Anthropic."""
        request = self._request(
            prompt, system_prompt, model, temperature, role, num_predict, response_schema
        )
        logger.debug(
            f"[ANTHROPIC] model={request['model']} max_tokens={request['max_tokens']} "
            f"thinking={request.get('thinking')} sampling={'temperature' in request}"
        )

        t0 = time.perf_counter()
        try:
            response = await self._client.messages.create(**request)
        except anthropic.APIStatusError as e:
            raise _unavailable(_status_cause(e), e) from e
        except anthropic.APIConnectionError as e:  # incluye el timeout
            raise _unavailable("sin_conexion", e) from e
        elapsed = time.perf_counter() - t0

        usage = response.usage
        logger.info(
            f"[ANTHROPIC] {request['model']} stop={response.stop_reason} "
            f"in={usage.input_tokens} out={usage.output_tokens} elapsed={elapsed:.1f}s"
        )
        if response.stop_reason == "refusal":
            details = response.stop_details
            raise LLMRefusalError(
                details.category if details else None, details.explanation if details else None
            )
        if response.stop_reason == "max_tokens":
            # Un acto truncado no se persiste.
            raise LLMResponseError(
                reason=f"respuesta truncada (max_tokens={request['max_tokens']})"
            )

        # Con pensamiento el primer bloque es de razonamiento: solo cuentan los bloques de texto.
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            elapsed_s=elapsed,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

    async def close(self) -> None:
        """Cierra el cliente HTTP del SDK."""
        close = getattr(self._client, "close", None)
        if close:
            await close()
