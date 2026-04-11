from typing import Optional


class MockLLMAdapter:
    """Implementación de LLMProvider para tests que devuelve respuestas predefinidas."""
    
    def __init__(self, response_to_return: str = "Respuesta del modelo mock."):
        self.response = response_to_return

    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        model: Optional[str] = None, 
        temperature: float = 0.7
    ) -> str:
        # Devuelve la respuesta predefinida para simular al LLM
        return self.response
