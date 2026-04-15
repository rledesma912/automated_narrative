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
            "num_predict": 4000,
        }

        payload = {
            "model": model_name,
            "prompt": full_prompt,
            "stream": True,
            "options": options,
            "keep_alive": "30m",
        }

        content = ""
        final_context = None

        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            async with client.stream("POST", self.base_url, json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if content_part := data.get("response"):
                        content += content_part
                    if data.get("done"):
                        final_context = data.get("context")
                        break

        return LLMResponse(text=content, context=final_context)

    async def close(self) -> None:
        """Close connection (no-op for Ollama)."""
        pass
