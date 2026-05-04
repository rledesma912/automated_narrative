"""Factorías para la creación de componentes de infraestructura."""

import logging

from src.config import settings
from src.domain.interfaces import LLMProvider
from src.infrastructure.adapters import (
    AnthropicAdapter,
    GeminiCLIAdapter,
    MockLLMAdapter,
    OllamaAdapter,
)

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factoría para instanciar proveedores de LLM."""

    @staticmethod
    def get_provider(use_mock: bool = False, provider: str | None = None) -> LLMProvider:
        """Retorna una instancia de LLMProvider según la configuración."""
        if use_mock:
            logger.info("[FACTORY] Usando proveedor Mock (Simulado)")
            return MockLLMAdapter()

        selected_provider = provider or settings.llm_provider

        if selected_provider == "gemini":
            logger.info(
                f"[FACTORY] Instanciando proveedor Gemini CLI ({settings.gemini_model_name})"
            )
            return GeminiCLIAdapter()

        if selected_provider == "anthropic":
            logger.info(f"[FACTORY] Instanciando proveedor Anthropic ({settings.anthropic_model})")
            return AnthropicAdapter()

        ollama_model = settings.role_config("voz").get("model", "mistral:latest")
        logger.info(f"[FACTORY] Instanciando proveedor Ollama ({ollama_model})")
        return OllamaAdapter()
