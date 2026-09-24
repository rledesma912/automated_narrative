"""Anthropic API adapter (Spec-480: al día con Claude Sonnet 5 / Opus 5)."""

import logging
import time

import anthropic

from src.config import settings
from src.domain.exceptions import LLMRefusalError, LLMResponseError
from src.domain.interfaces import LLMResponse

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


class AnthropicAdapter:
    """Adapter para la API de Anthropic.

    Config por rol (perfil): `model`, `num_predict` (→ max_tokens), `temperature` (solo
    modelos con sampling), `thinking` (`adaptive` | `disabled`; sin valor no se manda y el
    modelo usa su default — en Sonnet 5 / Opus 5 eso es pensar) y `effort`.
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
    ) -> dict:
        role_cfg = settings.role_config(role) if role else {}
        model_name = model or role_cfg.get("model") or self.default_model
        thinking = role_cfg.get("thinking")

        max_tokens = int(num_predict or role_cfg.get("num_predict") or _DEFAULT_MAX_TOKENS)
        if thinking != "disabled":
            # Adaptativo explícito, o el default de los modelos que piensan por defecto.
            max_tokens = max(max_tokens, _THINKING_MIN_MAX_TOKENS)

        request: dict = {
            "model": model_name,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            request["system"] = system_prompt
        if thinking in ("adaptive", "disabled"):
            request["thinking"] = {"type": thinking}
        if role_cfg.get("effort"):
            request["output_config"] = {"effort": role_cfg["effort"]}
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
        **kwargs,
    ) -> LLMResponse:
        """Genera texto con la API de Anthropic."""
        request = self._request(prompt, system_prompt, model, temperature, role, num_predict)
        logger.debug(
            f"[ANTHROPIC] model={request['model']} max_tokens={request['max_tokens']} "
            f"thinking={request.get('thinking')} sampling={'temperature' in request}"
        )

        t0 = time.perf_counter()
        try:
            response = await self._client.messages.create(**request)
        except anthropic.AuthenticationError as e:
            raise RuntimeError(f"[ANTHROPIC] API key inválida: {e}") from e
        except anthropic.RateLimitError as e:
            raise RuntimeError(f"[ANTHROPIC] Rate limit alcanzado: {e}") from e
        except anthropic.BadRequestError as e:
            raise RuntimeError(f"[ANTHROPIC] Request inválido: {e}") from e
        except anthropic.APIStatusError as e:
            raise RuntimeError(f"[ANTHROPIC] Error {e.status_code} de la API: {e}") from e
        except anthropic.APIConnectionError as e:
            raise RuntimeError(f"[ANTHROPIC] Sin conexión con la API: {e}") from e
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
