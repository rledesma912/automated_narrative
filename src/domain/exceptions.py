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


class LLMProviderError(NarrativeError):
    """Error en la llamada al proveedor LLM."""

    def __init__(self, provider: str, reason: str):
        super().__init__(
            f"Error del proveedor LLM '{provider}': {reason}",
            details={"provider": provider, "reason": reason},
        )
        self.provider = provider


class PromptTemplateError(NarrativeError):
    """Template de prompt no encontrado o inválido."""

    def __init__(self, filename: str):
        super().__init__(
            f"Template de prompt no encontrado: {filename}",
            details={"filename": filename},
        )
        self.filename = filename


class ParseError(NarrativeError):
    """Error al parsear la respuesta del LLM."""

    def __init__(self, role: str, reason: str):
        super().__init__(
            f"Error de parseo en rol '{role}': {reason}",
            details={"role": role, "reason": reason},
        )
        self.role = role
