"""CLI Exceptions for NarrativeForge."""


class CLIError(BaseException):
    """Base exception for CLI errors."""

    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class ValidationError(CLIError):
    """Raised when CLI argument validation fails."""

    def __init__(self, message: str):
        super().__init__(f"Validation error: {message}", exit_code=2)


class StoryNotFoundError(CLIError):
    """Raised when a story is not found in the database."""

    def __init__(self, story_id: str):
        super().__init__(f"Story not found: {story_id}", exit_code=3)


class OllamaConnectionError(CLIError):
    """Raised when cannot connect to Ollama."""

    def __init__(self, message: str = "Cannot connect to Ollama"):
        super().__init__(f"Ollama connection error: {message}", exit_code=4)


class GenerationError(CLIError):
    """Raised when story generation fails."""

    def __init__(self, message: str):
        super().__init__(f"Generation error: {message}", exit_code=5)


class ExportError(CLIError):
    """Raised when export fails."""

    def __init__(self, message: str):
        super().__init__(f"Export error: {message}", exit_code=6)
