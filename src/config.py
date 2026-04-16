"""Configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API
    env: str = "dev"
    api_host: str = "0.0.0.0:8010"

    # LLM
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "qwen3.5:9b"
    llm_model_temperature: float = 0.6

    # Database
    database_url: str = "sqlite+aiosqlite://stories.db"

    # Paths
    output_dir: str = "output_stories"
    prompts_dir: str = "config/prompts"

    @property
    def api_host_port(self) -> tuple[str, int]:
        """Parse host:port."""
        host, port = self.api_host.rsplit(":", 1)
        return host, int(port)


settings = Settings()
