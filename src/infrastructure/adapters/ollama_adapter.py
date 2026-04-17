"""Ollama adapter for LLM."""

import json

import httpx

from src.config import settings
from src.domain.interfaces import LLMResponse


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
    ) -> LLMResponse:
        """Generate text with Ollama."""
        model_name = model or settings.llm_model
        temp = temperature or settings.llm_model_temperature

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        options = {
            "temperature": temp,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "num_ctx": 4096,
            "num_predict": 2048,  # Increased
        }

        payload = {
            "model": model_name,
            "prompt": full_prompt,
            "stream": False,  # Non-streaming for reliability
            "options": options,
            "keep_alive": "30m",
        }

        content = ""

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.post(self.base_url, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("response", "")

        return LLMResponse(text=content)

    async def close(self) -> None:
        """Close connection (no-op for Ollama)."""
        pass
