"""Tests for MockLLMAdapter."""

import pytest

from src.infrastructure.adapters import MockLLMAdapter


class TestMockLLMAdapter:
    """Tests for MockLLMAdapter."""

    @pytest.mark.asyncio
    async def test_generate_returns_response(self):
        """Test that generate returns a response."""
        adapter = MockLLMAdapter(fixed_response="Test response")

        response = await adapter.generate("prompt text")

        assert response.text == "Test response"
        assert response.context is None

    @pytest.mark.asyncio
    async def test_generate_increments_call_count(self):
        """Test that call count is incremented."""
        adapter = MockLLMAdapter(fixed_response="Response")

        await adapter.generate("prompt 1")
        await adapter.generate("prompt 2")
        await adapter.generate("prompt 3")

        assert adapter.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_with_custom_response(self):
        """Test with custom response text."""
        adapter = MockLLMAdapter(fixed_response="Custom text")

        response = await adapter.generate("any prompt")

        assert response.text == "Custom text"

    @pytest.mark.asyncio
    async def test_close_is_noop(self):
        """Test that close is a no-op."""
        adapter = MockLLMAdapter()

        await adapter.close()

        assert adapter.call_count == 0
