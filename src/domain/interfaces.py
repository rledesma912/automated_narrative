"""Ports (interfaces) for the domain."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.models import Beat, Story


class LLMResponse:
    """Response from LLM."""

    def __init__(self, text: str, context: list[int] | None = None, elapsed_s: float = 0.0):
        self.text = text
        self.context = context
        self.elapsed_s = elapsed_s
        self.word_count = len(text.split())


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str = "mistral:latest",
        temperature: float = 0.6,
        role: str | None = None,
        num_ctx: int | None = None,
        num_predict: int | None = None,
    ) -> LLMResponse:
        """Generate text with LLM. `role` permite al adapter leer config específica del rol."""
        ...

    async def close(self) -> None:
        """Close connection."""
        ...


class StoryRepository(Protocol):
    """Protocol for Story repositories."""

    async def save(self, story: Story) -> Story:
        """Save a story."""
        ...

    async def get_by_id(self, story_id: UUID) -> Story | None:
        """Get story by ID."""
        ...

    async def update(self, story: Story) -> Story:
        """Update a story."""
        ...

    async def list_all(self) -> list[Story]:
        """List all stories."""
        ...


class BeatRepository(Protocol):
    """Protocol for Beat repositories."""

    async def save(self, beat: Beat) -> Beat:
        """Save a beat."""
        ...

    async def get_by_story(self, story_id: UUID) -> list[Beat]:
        """Get all beats for a story."""
        ...

    async def get_by_number(self, story_id: UUID, number: int) -> Beat | None:
        """Get beat by number."""
        ...

    async def update(self, beat: Beat) -> Beat:
        """Update a beat."""
        ...
