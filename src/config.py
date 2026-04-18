"""Configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API
    env: str = "dev"
    api_host: str = "0.0.0.0:8010"

    # LLM
    llm_provider: str = "ollama"  # ollama | gemini
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "mistral:latest"
    llm_model_temperature: float = 0.6
    state_extractor_model: str = "mistral:latest"
    state_extractor_temperature: float = 0.3
    director_temperature: float = 0.4
    voz_temperature: float = 0.6
    # Gemini CLI
    gemini_cli_command: str = "gemini"
    gemini_model_name: str = "gemini-1.5-pro-latest"

    # Database
    database_url: str = "sqlite+aiosqlite://stories.db"

    # Paths
    output_dir: str = "output_stories"
    prompts_dir: str = "config/prompts"
    input_dir: str = "input_stories"

    # Prompt filenames
    prompt_file_voice: str = "voice.md"
    prompt_file_system: str = "system.md"
    prompt_file_journal: str = "journal.md"

    @property
    def api_host_port(self) -> tuple[str, int]:
        """Parse host:port."""
        host, port = self.api_host.rsplit(":", 1)
        return host, int(port)


settings = Settings()
