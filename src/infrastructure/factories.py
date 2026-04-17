"""Factorías para la creación de componentes de infraestructura."""

from src.cli.logger import logger
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.infrastructure.adapters import GeminiCLIAdapter, MockLLMAdapter, OllamaAdapter


class LLMFactory:
    """Factoría para instanciar proveedores de LLM."""

    @staticmethod
    def get_provider(use_mock: bool = False, provider: str | None = None) -> LLMProvider:
        """
        Retorna una instancia de LLMProvider según la configuración.

        Args:
            use_mock: Si es True, siempre retorna MockLLMAdapter.
            provider: Si se especifica, ignora el valor de settings.llm_provider.
        """
        if use_mock:
            logger.info("[FACTORY] Usando proveedor Mock (Simulado)", module="llm_factory")
            return MockLLMAdapter()

        selected_provider = provider or settings.llm_provider

        if selected_provider == "gemini":
            logger.info(
                f"[FACTORY] Instanciando proveedor Gemini CLI ({settings.gemini_model_name})",
                module="llm_factory",
            )
            return GeminiCLIAdapter()

        # Por defecto usamos Ollama
        logger.info(
            f"[FACTORY] Instanciando proveedor Ollama ({settings.llm_model})", module="llm_factory"
        )
        return OllamaAdapter()
