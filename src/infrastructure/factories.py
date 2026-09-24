"""Factorías para la creación de componentes de infraestructura."""

import logging

from src.config import LLM_ROLES, settings
from src.domain.interfaces import LLMProvider
from src.infrastructure.adapters import (
    AnthropicAdapter,
    GeminiCLIAdapter,
    MockLLMAdapter,
    OllamaAdapter,
    RoleRoutingAdapter,
)

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factoría para instanciar proveedores de LLM."""

    @staticmethod
    def get_provider(use_mock: bool = False, provider: str | None = None) -> LLMProvider:
        """Retorna una instancia de LLMProvider según la configuración.

        Spec-480: si los roles del perfil usan proveedores distintos (p. ej. la Voz en
        Anthropic y el resto en Ollama), devuelve un `RoleRoutingAdapter` con un adapter
        por proveedor. Con un solo proveedor, el adapter de siempre.
        """
        if use_mock:
            logger.info("[FACTORY] Usando proveedor Mock (Simulado)")
            return MockLLMAdapter()

        if provider:
            return LLMFactory._single(provider)

        by_role = {role: settings.role_provider(role) for role in LLM_ROLES}
        providers = set(by_role.values())
        if len(providers) <= 1:
            return LLMFactory._single(providers.pop() if providers else settings.llm_provider)

        adapters = {p: LLMFactory._single(p) for p in sorted(providers)}
        default = adapters.get(settings.llm_provider) or next(iter(adapters.values()))
        logger.info(f"[FACTORY] Perfil mixto por rol: {by_role}")
        return RoleRoutingAdapter({r: adapters[p] for r, p in by_role.items()}, default=default)

    @staticmethod
    def _single(selected_provider: str) -> LLMProvider:
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
