"""Domain exceptions."""


class NarrativeError(Exception):
    """Base exception for domain."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class StoryNotFoundError(NarrativeError):
    """Story not found."""

    def __init__(self, story_id: str):
        super().__init__(
            f"Historia no encontrada: {story_id}",
            details={"story_id": story_id},
        )
        self.story_id = story_id
