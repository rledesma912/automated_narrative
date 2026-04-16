"""Package for adapters."""

from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter
from src.infrastructure.adapters.ollama_adapter import OllamaAdapter

__all__ = [
    "OllamaAdapter",
    "MockLLMAdapter",
]
