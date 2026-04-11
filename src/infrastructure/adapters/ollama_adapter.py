import httpx
import json
from typing import Optional
from src.config import settings

class OllamaAdapter:
    """Implementación de LLMProvider para Ollama local."""
    
    def __init__(self, host: str = settings.ollama_host):
        self.base_url = f"{host}/api/chat"
        # Timeout largo para generaciones de relatos largos
        self.timeout = httpx.Timeout(300.0, connect=10.0)

    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        model: Optional[str] = "qwen2.5:32b", 
        temperature: float = 0.7
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 16384  # Ventana de contexto amplia para historias
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                return result.get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            # En producción esto se loguearía, aquí relanzamos para que el orquestador maneje el retry
            raise ConnectionError(f"Error al conectar con Ollama: {e}")
        except Exception as e:
            raise RuntimeError(f"Error inesperado en el adaptador de Ollama: {e}")
