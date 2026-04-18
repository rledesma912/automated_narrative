"""Ollama adapter for LLM."""

import logging
import time

import httpx

from src.config import settings
from src.domain.interfaces import LLMResponse

logger = logging.getLogger(__name__)


class OllamaAdapter:
    """Adapter for Ollama API."""

    def __init__(self, host: str | None = None):
        self.base_url = (host or settings.ollama_host).rstrip("/") + "/api/generate"
        self.timeout = httpx.Timeout(1200.0, connect=10.0)

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        role: str | None = None,
    ) -> LLMResponse:
        """Generate text with Ollama.

        role: si se especifica, carga num_ctx/num_predict/stop desde llm_core_definitions.yaml.
        """
        role_cfg = settings.role_config(role) if role else {}

        model_name = model or role_cfg.get("model") or settings.llm_model
        temp = temperature if temperature is not None else float(role_cfg.get("temperature", settings.llm_model_temperature))

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        options: dict = {
            "temperature": temp,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "num_ctx": int(role_cfg.get("num_ctx", 4096)),
            "num_predict": int(role_cfg.get("num_predict", 2048)),
        }

        payload: dict = {
            "model": model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": options,
            "keep_alive": "30m",
        }

        stop_sequences = role_cfg.get("stop", [])
        if stop_sequences:
            payload["stop"] = stop_sequences

        logger.debug(
            f"[OLLAMA] model={model_name}, role={role}, temp={temp}, "
            f"num_ctx={options['num_ctx']}, num_predict={options['num_predict']}, "
            f"stop={stop_sequences}"
        )
        logger.debug(f"[OLLAMA] ===PROMPT_START===\n{full_prompt}\n===PROMPT_END===")

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.post(self.base_url, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("response", "")

        elapsed = time.perf_counter() - t0
        logger.debug(f"[OLLAMA] ===RESPONSE_START===\n{content}\n===RESPONSE_END===")
        logger.debug(f"[OLLAMA] elapsed={elapsed:.2f}s, len={len(content)}")

        return LLMResponse(text=content, elapsed_s=elapsed)

    async def close(self) -> None:
        """Close connection (no-op for Ollama)."""
        pass
