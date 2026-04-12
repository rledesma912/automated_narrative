from pathlib import Path
from typing import Optional

from src.config import settings
from src.domain.models import ActInput, NarrativeState, Story


class PromptBuilder:
    """Servicio encargado de construir los prompts para el LLM."""

    def __init__(self, prompts_dir: str = None):
        self.prompts_dir = Path(prompts_dir or settings.prompts_dir)
        self._system_template = None
        self._state_template = None

    def _load_prompt(self, filename: str) -> str:
        """Carga un prompt desde un archivo externo."""
        file_path = self.prompts_dir / filename
        if file_path.exists():
            return file_path.read_text(encoding="utf-8").strip()
        return ""

    @property
    def system_template(self) -> str:
        if self._system_template is None:
            self._system_template = self._load_prompt("system_prompt.md")
        return self._system_template

    @property
    def state_template(self) -> str:
        if self._state_template is None:
            self._state_template = self._load_prompt("state_prompt.md")
        return self._state_template

    def build_system_prompt(self, story: Story) -> str:
        template = self.system_template
        if template:
            if "{{" in template:
                reglas_str = "\n".join([f"- {r}" for r in story.reglas])
                return template.format(
                    atmosfera=story.atmosfera, relator=story.relator, reglas=reglas_str, protagonistas=story.protagonistas, escenarios=story.escenarios, sinopsis=story.sinopsis
                )
            return template
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

    def build_act_prompt(self, story: Story, act: ActInput, previous_state: Optional[NarrativeState] = None) -> str:
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

    def build_state_extraction_prompt(self, content: str) -> str:
        template = self.state_template
        if template:
            return template.replace("{{chapter_text}}", content)
        return (
            "Analiza el siguiente fragmento de un relato de terror y extrae "
            "el estado narrativo actual en formato JSON.\n\n"
            'FRAGMENTO:\n"""\n' + content + '\n"""\n\n'
            "Responde ÚNICAMENTE con un objeto JSON con esta estructura exacta:\n"
            '{"location": "Lugar actual de la escena",\n'
            '"characters": "Personajes presentes y su estado",\n'
            '"situation": "Breve resumen de lo que está pasando",\n'
            '"active_threat": "Peligro o amenaza inmediata (si hay)",\n'
            '"goal": "Qué intentan lograr los personajes ahora",\n'
            '"last_action": "La última acción importante que cerró el fragmento"}\n'
        )
