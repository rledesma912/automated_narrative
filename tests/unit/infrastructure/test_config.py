import pytest
from src.config import Settings
import os

def test_settings_load_sanitization():
    """Valida que la configuración se cargue correctamente desde el YAML."""
    # Instanciamos settings (usará el archivo real en config/sanitization.yaml)
    s = Settings()
    rules = s.sanitization
    
    assert "think" in rules.thinking_tags
    assert "thought" in rules.thinking_tags
    assert "deepseek-r1" in rules.model_overrides
    assert rules.model_overrides["deepseek-r1"]["strip_thinking"] is True

def test_settings_env_override():
    """Valida que las variables de entorno tengan prioridad (Patrón 12-factor)."""
    os.environ["OLLAMA_HOST"] = "http://remote-ollama:11434"
    s = Settings()
    assert s.ollama_host == "http://remote-ollama:11434"
    
    # Limpieza
    del os.environ["OLLAMA_HOST"]
