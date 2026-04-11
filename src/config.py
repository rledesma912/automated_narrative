import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class SanitizationSpecs(BaseModel):
    thinking_tags: List[str] = ["think", "thought"]
    noise_patterns: List[str] = []
    markdown_extraction_enabled: bool = Field(default=True, alias="markdown_extraction.enabled")
    model_overrides: Dict[str, Dict[str, Any]] = {}

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Entorno
    env: str = "dev"
    ollama_host: str = "http://localhost:11434"
    database_url: str = "sqlite+aiosqlite:///stories.db"
    
    # Rutas de Configuración
    sanitization_spec_path: str = "config/sanitization.yaml"
    
    # Propiedad para acceder a las reglas de sanitización ya cargadas
    @property
    def sanitization(self) -> SanitizationSpecs:
        config_path = Path(self.sanitization_spec_path)
        if not config_path.exists():
            return SanitizationSpecs()
        
        with open(config_path, "r", encoding="utf-8") as f:
            raw_yaml = yaml.safe_load(f)
            # Adaptamos el YAML plano al modelo anidado de Pydantic
            san_data = raw_yaml.get("sanitization", {})
            return SanitizationSpecs(
                thinking_tags=san_data.get("thinking_tags", []),
                noise_patterns=san_data.get("noise_patterns", []),
                model_overrides=san_data.get("model_overrides", {})
            )

# Instancia global de settings
settings = Settings()
