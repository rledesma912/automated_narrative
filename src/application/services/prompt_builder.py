from typing import Optional, List
from src.domain.models import Story, ActInput, NarrativeState

class PromptBuilder:
    """Servicio encargado de construir los prompts para el LLM."""
    
    @staticmethod
    def build_system_prompt(story: Story) -> str:
        reglas_str = "\n".join([f"- {r}" for r in story.reglas])
        return f"""Eres un experto escritor de relatos de terror y suspenso en español.
Tu estilo es {story.atmosfera}.
El relato es narrado por: {story.relator}.

REGLAS INMUTABLES QUE DEBES RESPETAR:
{reglas_str}

CONTEXTO GENERAL:
Protagonistas: {story.protagonistas}
Escenarios: {story.escenarios}
Sinopsis: {story.sinopsis}
"""

    @staticmethod
    def build_act_prompt(
        story: Story, 
        act: ActInput, 
        previous_state: Optional[NarrativeState] = None
    ) -> str:
        state_str = ""
        if previous_state:
            state_str = f"""
ESTADO NARRATIVO ACTUAL (Continuidad):
- Ubicación: {previous_state.location}
- Personajes presentes: {previous_state.characters}
- Situación: {previous_state.situation}
- Amenaza activa: {previous_state.active_threat}
- Objetivo actual: {previous_state.goal}
- Última acción importante: {previous_state.last_action}
"""
        
        return f"""{state_str}

MISIÓN DEL ACTO {act.number} — "{act.title}":
{act.mission}

INSTRUCCIONES:
- Escribe un capítulo inmersivo de al menos 400 palabras.
- Mantén el tono de terror y la atmósfera {story.atmosfera}.
- No incluyas introducciones ni despedidas, solo el relato narrativo.
- No uses formato JSON.
"""

    @staticmethod
    def build_state_extraction_prompt(content: str) -> str:
        return f"""Analiza el siguiente fragmento de un relato de terror y extrae el estado narrativo actual en formato JSON.

FRAGMENTO:
\"\"\"
{content}
\"\"\"

Responde ÚNICAMENTE con un objeto JSON con esta estructura exacta:
{{
  "location": "Lugar actual de la escena",
  "characters": "Personajes presentes y su estado",
  "situation": "Breve resumen de lo que está pasando",
  "active_threat": "Peligro o amenaza inmediata (si hay)",
  "goal": "Qué intentan lograr los personajes ahora",
  "last_action": "La última acción importante que cerró el fragmento"
}}
"""
