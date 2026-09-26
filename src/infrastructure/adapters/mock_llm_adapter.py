"""Mock LLM adapter for testing."""

import json

from src.domain.interfaces import LLMResponse
from src.infrastructure.adapters.mock_structured import mock_structured


class MockLLMAdapter:
    """Mock adapter for testing."""

    def __init__(self, fixed_response: str = "Contenido de ejemplo"):
        self.fixed_response = fixed_response
        self.call_count = 0

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str = "mock",
        temperature: float = 0.6,
        role: str | None = None,
        response_schema: dict | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate mock text (o un JSON coherente con el esquema pedido, Spec-530)."""
        self.call_count += 1
        if response_schema is not None:
            return LLMResponse(text=json.dumps(mock_structured(role, response_schema)))
        return LLMResponse(
            text=self.fixed_response,
            context=None,
        )

    async def close(self) -> None:
        """Close connection (no-op)."""
        pass
