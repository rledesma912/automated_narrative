"""Tests para LLMFactory."""

from unittest.mock import patch


from src.infrastructure.adapters import AnthropicAdapter, GeminiCLIAdapter, MockLLMAdapter, OllamaAdapter
from src.infrastructure.factories import LLMFactory


class TestLLMFactory:
    def test_use_mock_retorna_mock_adapter(self):
        result = LLMFactory.get_provider(use_mock=True)
        assert isinstance(result, MockLLMAdapter)

    def test_use_mock_ignora_provider(self):
        result = LLMFactory.get_provider(use_mock=True, provider="anthropic")
        assert isinstance(result, MockLLMAdapter)

    def test_provider_gemini_retorna_gemini_adapter(self):
        result = LLMFactory.get_provider(provider="gemini")
        assert isinstance(result, GeminiCLIAdapter)

    def test_provider_ollama_retorna_ollama_adapter(self):
        result = LLMFactory.get_provider(provider="ollama")
        assert isinstance(result, OllamaAdapter)

    def test_provider_default_retorna_ollama_adapter(self):
        with patch("src.infrastructure.factories.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_settings.llm_model = "mistral:latest"
            result = LLMFactory.get_provider()
        assert isinstance(result, OllamaAdapter)

    def test_provider_anthropic_retorna_anthropic_adapter(self):
        with patch("src.infrastructure.factories.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_settings.anthropic_model = "claude-opus-4-7"
            with patch(
                "src.infrastructure.adapters.anthropic_adapter.settings"
            ) as mock_adapter_settings:
                mock_adapter_settings.anthropic_api_key = "test-key"
                mock_adapter_settings.anthropic_model = "claude-opus-4-7"
                with patch("src.infrastructure.adapters.anthropic_adapter.anthropic.AsyncAnthropic"):
                    result = LLMFactory.get_provider(provider="anthropic")
        assert isinstance(result, AnthropicAdapter)
