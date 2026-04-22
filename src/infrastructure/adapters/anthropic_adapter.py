"""Anthropic API adapter."""

import logging
import time

import anthropic

from src.config import settings
from src.domain.interfaces import LLMResponse

logger = logging.getLogger(__name__)

# Prefijos de modelos que no aceptan parámetros de sampling (temperature, top_p, top_k)
_NO_SAMPLING_PREFIXES = ("claude-opus-4",)


class AnthropicAdapter:
    """Adapter para la API de Anthropic."""

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        key = api_key or settings.anthropic_api_key
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY no configurada. "
                "Agrégala al .env o exporta la variable de entorno."
            )
        self._client = anthropic.AsyncAnthropic(api_key=key)
        self.default_model = default_model or settings.anthropic_model

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        role: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Genera texto con la API de Anthropic."""
        model_name = model or self.default_model
        kwargs: dict = {
            "model": model_name,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        uses_sampling = not any(model_name.startswith(p) for p in _NO_SAMPLING_PREFIXES)
        if uses_sampling and temperature is not None:
            kwargs["temperature"] = temperature

        logger.debug(f"[ANTHROPIC] model={model_name}, sampling={uses_sampling}")
        logger.debug(f"[ANTHROPIC] prompt (primeros 500):\n{prompt[:500]}")

        t0 = time.perf_counter()
        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise RuntimeError(f"[ANTHROPIC] API key inválida: {e}") from e
        except anthropic.RateLimitError as e:
            raise RuntimeError(f"[ANTHROPIC] Rate limit alcanzado: {e}") from e
        except anthropic.BadRequestError as e:
            raise RuntimeError(f"[ANTHROPIC] Request inválido: {e}") from e
        elapsed = time.perf_counter() - t0

        text = response.content[0].text
        logger.debug(f"[ANTHROPIC] elapsed={elapsed:.2f}s, respuesta (primeros 300):\n{text[:300]}")
        return LLMResponse(text=text, elapsed_s=elapsed)

    async def close(self) -> None:
        """No-op: el cliente Anthropic no mantiene conexión persistente."""
        pass
