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


class NarrativeLiteracyError(NarrativeError):
    """El modelo falló la auditoría de alfabetismo narrativo en modo estricto (assertive)."""

    def __init__(self, reason: str):
        super().__init__(
            f"Respuesta pedagógica rechazada: {reason}",
            details={"reason": reason},
        )
        self.reason = reason


class LLMResponseError(NarrativeError):
    """El LLM retornó una respuesta inválida o vacía."""

    def __init__(self, reason: str, raw_response: str | None = None):
        super().__init__(
            f"Respuesta del LLM inválida: {reason}",
            details={"reason": reason, "raw_response": raw_response},
        )
        self.reason = reason
        self.raw_response = raw_response


class DatabaseError(NarrativeError):
    """Error de base de datos durante persistencia."""

    def __init__(self, reason: str, operation: str | None = None):
        super().__init__(
            f"Error de base de datos: {reason}",
            details={"reason": reason, "operation": operation},
        )
        self.reason = reason
        self.operation = operation
