import json
import re
from typing import Optional

from src.application.services.prompt_builder import PromptBuilder
from src.domain.interfaces import LLMProvider
from src.domain.models import NarrativeState


class OllamaStateExtractor:
    """Implementación de StateExtractor que usa Ollama para analizar el relato."""
    
    def __init__(self, llm: LLMProvider, model: str = "gemma4:e4b"):
        self.llm = llm
        self.model = model
        self.prompt_builder = PromptBuilder()

    async def extract_state(self, act_content: str, previous_state: Optional[NarrativeState] = None) -> NarrativeState:
        """Llama al LLM para extraer el estado narrativo actual del capítulo."""
        
        prompt = self.prompt_builder.build_state_extraction_prompt(act_content)
        
        try:
            raw_response = await self.llm.generate(
                prompt=prompt,
                system_prompt="Eres un extractor de datos precisos. Responde solo en JSON.",
                model=self.model,
                temperature=0.1 # Muy baja para evitar alucinaciones
            )
            
            # Limpiar posible basura del LLM (explicaciones, markdown tags)
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if not json_match:
                # Si falla, devolvemos el estado anterior como fallback para no romper la cadena
                return previous_state or NarrativeState()
                
            json_data = json.loads(json_match.group(0))
            
            return NarrativeState(
                location=json_data.get("location", ""),
                characters=json_data.get("characters", ""),
                situation=json_data.get("situation", ""),
                active_threat=json_data.get("active_threat", ""),
                goal=json_data.get("goal", ""),
                last_action=json_data.get("last_action", "")
            )
            
        except Exception:
            # Fallback seguro: si el LLM falla, mantenemos el estado anterior
            return previous_state or NarrativeState()
