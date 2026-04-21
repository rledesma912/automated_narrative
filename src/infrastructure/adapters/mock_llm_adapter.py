"""Mock LLM adapter for testing."""

from src.domain.interfaces import LLMResponse


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
        **kwargs,
    ) -> LLMResponse:
        """Generate mock text."""
        self.call_count += 1
        return LLMResponse(
            text=self.fixed_response,
            context=None,
        )

    async def close(self) -> None:
        """Close connection (no-op)."""
        pass
