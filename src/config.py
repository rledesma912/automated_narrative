from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResponseFilters(BaseModel):
    thinking_tags: List[str] = ["think", "thought"]
    noise_patterns: List[str] = []
    markdown_extraction_enabled: bool = Field(default=True, alias="markdown_extraction.enabled")
    model_overrides: Dict[str, Dict[str, Any]] = {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Entorno
    env: str = "dev"
    api_host: str = "0.0.0.0:8000"
    ollama_host: str = "http://localhost:11434"
    database_url: str = "sqlite+aiosqlite:///stories.db"

    # Rutas de Configuración
    llm_response_filters_path: str = "config/llm_response_filters.yaml"

    # Rutas de directorios
    output_dir: str = "output_stories"
    template_dir: str = "templates"
    prompts_dir: str = "config/prompts"

    @property
    def api_host_port(self) -> Tuple[str, int]:
        host, port_str = self.api_host.rsplit(":", 1)
        return host, int(port_str)

    @property
    def response_filters(self) -> ResponseFilters:
        config_path = Path(self.llm_response_filters_path)
        if not config_path.exists():
            return ResponseFilters()

        with open(config_path, "r", encoding="utf-8") as f:
            raw_yaml = yaml.safe_load(f)
            san_data = raw_yaml.get("llm_response_filters", {})
            return ResponseFilters(
                thinking_tags=san_data.get("thinking_tags", []),
                noise_patterns=san_data.get("noise_patterns", []),
                model_overrides=san_data.get("model_overrides", {}),
            )


settings = Settings()
