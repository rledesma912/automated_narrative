"""Tests for CLI exceptions."""

from src.cli.exceptions import (
    CLIError,
    ExportError,
    GenerationError,
    OllamaConnectionError,
    StoryNotFoundError,
    ValidationError,
)


class TestCLIError:
    """Tests for CLI exceptions."""

    def test_cli_error_default_exit_code(self):
        """Test default exit code is 1."""
        err = CLIError("Test error")
        assert err.exit_code == 1
        assert err.message == "Test error"

    def test_cli_error_custom_exit_code(self):
        """Test custom exit code."""
        err = CLIError("Test error", exit_code=2)
        assert err.exit_code == 2

    def test_cli_error_str(self):
        """Test string representation."""
        err = CLIError("Test error")
        assert str(err) == "Test error"


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_message(self):
        """Test validation error message."""
        err = ValidationError("Invalid input")
        assert "validación" in err.message.lower()
        assert "Invalid input" in err.message
        assert err.exit_code == 2


class TestStoryNotFoundError:
    """Tests for StoryNotFoundError."""

    def test_story_not_found_message(self):
        """Test story not found message."""
        err = StoryNotFoundError("12345")
        assert "12345" in err.message
        assert err.exit_code == 3


class TestOllamaConnectionError:
    """Tests for OllamaConnectionError."""

    def test_ollama_connection_error_default(self):
        """Test default message."""
        err = OllamaConnectionError()
        assert "Ollama" in err.message
        assert err.exit_code == 4

    def test_ollama_connection_error_custom(self):
        """Test custom message."""
        err = OllamaConnectionError("Server down")
        assert "Server down" in err.message


class TestGenerationError:
    """Tests for GenerationError."""

    def test_generation_error_message(self):
        """Test generation error message."""
        err = GenerationError("Failed to generate")
        assert "generación" in err.message.lower()
        assert "Failed to generate" in err.message
        assert err.exit_code == 5


class TestExportError:
    """Tests for ExportError."""

    def test_export_error_message(self):
        """Test export error message."""
        err = ExportError("File not found")
        assert "exportación" in err.message.lower()
        assert "File not found" in err.message
        assert err.exit_code == 6
