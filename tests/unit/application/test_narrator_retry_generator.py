"""Tests para NarratorRetryGenerator."""

import pytest

from src.application.services.narrator_retry_generator import NarratorRetryGenerator
from src.domain.interfaces import LLMResponse


def _make_llm(*responses: str):
    """Retorna un mock LLM que devuelve respuestas en secuencia."""
    idx = 0

    class SeqLLM:
        async def generate(self, prompt, **kwargs):
            nonlocal idx
            text = responses[min(idx, len(responses) - 1)]
            idx += 1
            return LLMResponse(text=text, context=None)

        async def close(self):
            pass

    return SeqLLM(), lambda: idx


class TestNarratorRetryGenerator:
    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        """Respuesta normal — no hay retry, llama al LLM una sola vez."""
        llm, get_calls = _make_llm("El molino crujía bajo la tormenta.")
        gen = NarratorRetryGenerator(llm)

        response = await gen.generate_with_retry("prompt", None, "model", 0.7)

        assert "molino" in response.text
        assert get_calls() == 1

    @pytest.mark.asyncio
    async def test_retry_on_refusal(self):
        """Primer intento es refusal — genera retry hasta obtener contenido."""
        llm, get_calls = _make_llm("Lo siento, no puedo escribir eso.", "El relato continúa.")
        gen = NarratorRetryGenerator(llm)

        response = await gen.generate_with_retry("prompt", None, "model", 0.7, max_retries=2)

        assert "relato" in response.text
        assert get_calls() == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_returns_last_response(self):
        """Todos los intentos son refusals — retorna el último response."""
        llm, get_calls = _make_llm(
            "No puedo cumplir con eso.",
            "No es apropiado escribir esto.",
            "Lo siento, no puedo.",
        )
        gen = NarratorRetryGenerator(llm)

        response = await gen.generate_with_retry("prompt", None, "model", 0.7, max_retries=2)

        assert get_calls() == 3
        assert "lo siento" in response.text.lower() or "no" in response.text.lower()

    @pytest.mark.asyncio
    async def test_rephrase_prompt_called_on_refusal(self):
        """El prompt se modifica tras un refusal — incluye el hint de rephrase."""
        prompts_received = []

        class SpyLLM:
            async def generate(self, prompt, **kwargs):
                prompts_received.append(prompt)
                if len(prompts_received) == 1:
                    return LLMResponse(text="Lo siento, no puedo.", context=None)
                return LLMResponse(text="Contenido generado.", context=None)

            async def close(self):
                pass

        gen = NarratorRetryGenerator(SpyLLM())
        await gen.generate_with_retry("prompt original", None, "model", 0.7)

        assert len(prompts_received) == 2
        assert "ATTENTION" in prompts_received[1]
        assert prompts_received[0] == "prompt original"

    def test_rephrase_prompt_appends_hint(self):
        """_rephrase_prompt añade el hint al prompt original."""
        from src.infrastructure.adapters import MockLLMAdapter

        gen = NarratorRetryGenerator(MockLLMAdapter())

        result = gen._rephrase_prompt("Base prompt.")

        assert result.startswith("Base prompt.")
        assert "ATTENTION" in result
        assert "horror story" in result
