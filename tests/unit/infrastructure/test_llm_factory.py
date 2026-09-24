"""Tests para LLMFactory."""

from unittest.mock import patch

from src.infrastructure.adapters import (
    AnthropicAdapter,
    GeminiCLIAdapter,
    MockLLMAdapter,
    OllamaAdapter,
)
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
                with patch(
                    "src.infrastructure.adapters.anthropic_adapter.anthropic.AsyncAnthropic"
                ):
                    result = LLMFactory.get_provider(provider="anthropic")
        assert isinstance(result, AnthropicAdapter)


class TestPerfilMixto:
    """Spec-480 T0.3: un adapter por proveedor, ruteado por rol."""

    def _profile(self, monkeypatch, voz_provider: str | None):
        import src.config as config

        voz = {"model": "claude-sonnet-5"}
        if voz_provider:
            voz["provider"] = voz_provider
        monkeypatch.setattr(
            config,
            "_profile",
            {
                "provider": "ollama",
                "ollama": {"host": "http://localhost:11434"},
                "roles": {
                    "story_analyst": {"model": "gemma3:12b"},
                    "director": {"model": "gemma3:12b"},
                    "voz": voz,
                    "journal": {"model": "gemma3:12b"},
                },
            },
        )

    def test_un_solo_proveedor_devuelve_el_adapter_de_siempre(self, monkeypatch):
        self._profile(monkeypatch, None)
        assert isinstance(LLMFactory.get_provider(), OllamaAdapter)

    def test_mixto_rutea_cada_rol_a_su_proveedor(self, monkeypatch):
        from src.infrastructure.adapters import RoleRoutingAdapter

        self._profile(monkeypatch, "anthropic")
        with (
            patch("src.infrastructure.adapters.anthropic_adapter.settings") as adapter_settings,
            patch("src.infrastructure.adapters.anthropic_adapter.anthropic.AsyncAnthropic"),
        ):
            adapter_settings.anthropic_api_key = "test-key"  # sin requests reales
            adapter_settings.anthropic_model = "claude-sonnet-5"
            router = LLMFactory.get_provider()

        assert isinstance(router, RoleRoutingAdapter)
        assert isinstance(router.adapter_for("voz"), AnthropicAdapter)
        local = router.adapter_for("journal")
        assert isinstance(local, OllamaAdapter)
        # Los roles locales comparten un único adapter de Ollama.
        assert router.adapter_for("director") is local and router.adapter_for(None) is local

    def test_provider_explicito_ignora_el_ruteo(self, monkeypatch):
        self._profile(monkeypatch, "anthropic")
        assert isinstance(LLMFactory.get_provider(provider="ollama"), OllamaAdapter)
