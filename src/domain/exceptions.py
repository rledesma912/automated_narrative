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


class BeatNotFoundError(NarrativeError):
    """Beat not found."""

    def __init__(self, story_id: str, beat_number: int):
        super().__init__(
            f"Beat {beat_number} no encontrado en historia {story_id}",
            details={"story_id": story_id, "beat_number": beat_number},
        )
        self.story_id = story_id
        self.beat_number = beat_number


class PlanGenerationError(NarrativeError):
    """Error generating plan."""

    def __init__(self, reason: str):
        super().__init__(
            f"Error generando plan: {reason}",
            details={"reason": reason},
        )


class InvalidInputError(NarrativeError):
    """Invalid input error."""

    def __init__(self, field: str, message: str):
        super().__init__(
            f"Validación fallida en {field}: {message}",
            details={"field": field},
        )
        self.field = field
