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


class LLMRefusalError(LLMResponseError):
    """El modelo declinó la solicitud (`stop_reason: refusal`, Spec-480)."""

    def __init__(self, category: str | None, explanation: str | None = None):
        super().__init__(
            f"el modelo declinó la solicitud (categoría: {category or 'sin categoría'})",
            raw_response=explanation,
        )
        self.category = category


class DatabaseError(NarrativeError):
    """Error de base de datos durante persistencia."""

    def __init__(self, reason: str, operation: str | None = None):
        super().__init__(
            f"Error de base de datos: {reason}",
            details={"reason": reason, "operation": operation},
        )
        self.reason = reason
        self.operation = operation


class InvalidStoryInputError(NarrativeError):
    """Datos de entrada de una historia rechazados por el catálogo o el dominio.

    La API la responde como 422 y el CLI como "Error de validación".
    """


class InvalidGenreError(InvalidStoryInputError):
    """Género o par género/subgénero que no está en el catálogo (Spec-440 §2)."""

    def __init__(self, genero: str, subgenero: str = ""):
        if subgenero:
            msg = f"El subgénero '{subgenero}' no corresponde al género '{genero}'"
        else:
            msg = f"El género '{genero}' no existe en el catálogo"
        super().__init__(msg, details={"genero": genero, "subgenero": subgenero})
        self.genero = genero
        self.subgenero = subgenero


class InvalidAuthoringError(InvalidStoryInputError):
    """Dirección, taller o escaleta inválidos (Spec-530)."""

    def __init__(self, message: str):
        super().__init__(message)


class InvalidEntityError(InvalidStoryInputError):
    """Entidades narrativas inválidas: cantidad, largo, nivel o naturaleza (Spec-450 §1)."""

    def __init__(self, message: str):
        super().__init__(message)
