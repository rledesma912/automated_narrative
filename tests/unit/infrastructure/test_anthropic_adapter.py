"""Tests para AnthropicAdapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.interfaces import LLMResponse
from src.infrastructure.adapters.anthropic_adapter import AnthropicAdapter


def _make_response(text: str) -> MagicMock:
    """Crea un mock de respuesta de la API de Anthropic."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


class TestAnthropicAdapterInit:
    def test_sin_api_key_lanza_valueerror(self):
        with patch("src.infrastructure.adapters.anthropic_adapter.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            mock_settings.anthropic_model = "claude-opus-4-7"
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                AnthropicAdapter()

    def test_con_api_key_parametro_no_lanza(self):
        from src.config import settings

        with patch("src.infrastructure.adapters.anthropic_adapter.anthropic.AsyncAnthropic"):
            adapter = AnthropicAdapter(api_key="test-key")
            assert adapter.default_model == settings.anthropic_model

    def test_default_model_override(self):
        with patch("src.infrastructure.adapters.anthropic_adapter.anthropic.AsyncAnthropic"):
            adapter = AnthropicAdapter(api_key="test-key", default_model="claude-haiku-4-5")
            assert adapter.default_model == "claude-haiku-4-5"


class TestAnthropicAdapterGenerate:
    @pytest.fixture
    def adapter(self):
        with patch(
            "src.infrastructure.adapters.anthropic_adapter.anthropic.AsyncAnthropic"
        ) as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            adapter = AnthropicAdapter(api_key="test-key")
            adapter._client = mock_client
            return adapter

    @pytest.mark.asyncio
    async def test_retorna_llm_response(self, adapter):
        adapter._client.messages.create = AsyncMock(
            return_value=_make_response("Era una noche oscura.")
        )
        result = await adapter.generate("prompt")
        assert isinstance(result, LLMResponse)
        assert result.text == "Era una noche oscura."

    @pytest.mark.asyncio
    async def test_elapsed_s_es_float(self, adapter):
        adapter._client.messages.create = AsyncMock(return_value=_make_response("texto"))
        result = await adapter.generate("prompt")
        assert isinstance(result.elapsed_s, float)

    @pytest.mark.asyncio
    async def test_opus4_no_envia_temperature(self, adapter):
        adapter._client.messages.create = AsyncMock(return_value=_make_response("texto"))
        await adapter.generate("prompt", model="claude-opus-4-7", temperature=0.7)
        call_kwargs = adapter._client.messages.create.call_args.kwargs
        assert "temperature" not in call_kwargs

    @pytest.mark.asyncio
    async def test_modelo_no_opus4_envia_temperature(self, adapter):
        adapter._client.messages.create = AsyncMock(return_value=_make_response("texto"))
        await adapter.generate("prompt", model="claude-haiku-4-5", temperature=0.5)
        call_kwargs = adapter._client.messages.create.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.5

    @pytest.mark.asyncio
    async def test_system_prompt_se_pasa_como_parametro(self, adapter):
        adapter._client.messages.create = AsyncMock(return_value=_make_response("texto"))
        await adapter.generate("prompt", system_prompt="Eres un narrador.")
        call_kwargs = adapter._client.messages.create.call_args.kwargs
        assert call_kwargs.get("system") == "Eres un narrador."

    @pytest.mark.asyncio
    async def test_sin_system_prompt_no_incluye_system(self, adapter):
        adapter._client.messages.create = AsyncMock(return_value=_make_response("texto"))
        await adapter.generate("prompt")
        call_kwargs = adapter._client.messages.create.call_args.kwargs
        assert "system" not in call_kwargs

    @pytest.mark.asyncio
    async def test_authentication_error_lanza_runtime(self, adapter):
        import anthropic as anthropic_module

        adapter._client.messages.create = AsyncMock(
            side_effect=anthropic_module.AuthenticationError(
                message="invalid", response=MagicMock(), body={}
            )
        )
        with pytest.raises(RuntimeError, match="API key inválida"):
            await adapter.generate("prompt")

    @pytest.mark.asyncio
    async def test_rate_limit_error_lanza_runtime(self, adapter):
        import anthropic as anthropic_module

        adapter._client.messages.create = AsyncMock(
            side_effect=anthropic_module.RateLimitError(
                message="rate limit", response=MagicMock(), body={}
            )
        )
        with pytest.raises(RuntimeError, match="Rate limit"):
            await adapter.generate("prompt")

    @pytest.mark.asyncio
    async def test_close_es_no_op(self, adapter):
        await adapter.close()
