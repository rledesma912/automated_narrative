"""PromptBuilder - construye los prompts para el LLM."""

from pathlib import Path

from src.config import settings
from src.domain.models import Beat, Story


class PromptBuilder:
    """Servicio para construir prompts."""

    def __init__(self, prompts_dir: str | None = None):
        self.prompts_dir = Path(prompts_dir or settings.prompts_dir)
        self._system_template = None
        self._planner_template = None

    def _load_prompt(self, filename: str) -> str:
        """Carga una plantilla de prompt."""
        file_path = self.prompts_dir / filename
        if file_path.exists():
            return file_path.read_text(encoding="utf-8").strip()
        return ""

    def build_system_prompt(self, story: Story) -> str:
        """Build el system prompt base."""
        if self._system_template is None:
            self._system_template = self._load_prompt("system.md")

        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"

        if self._system_template:
            return self._system_template.format(
                atmosfera=story.atmosfera,
                relator=story.relator,
                reglas=reglas_str,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                sinopsis=story.sinopsis,
            )

        return f"""Eres un experto escritor de relatos de terror en español.
Tu estilo es: {story.atmosfera}
El relator es: {story.relator}

REGLAS:
{reglas_str}

Protagonistas: {story.protagonista}
Escenarios: {story.escenarios}
Sinopsis: {story.sinopsis}
"""

    def build_planner_prompt(self, story: Story, num_beats: int = 8) -> str:
        """Build el prompt del Director para generar la escaleta."""
        if self._planner_template is None:
            self._planner_template = self._load_prompt("planner.md")

        if self._planner_template:
            return self._planner_template.format(
                title=story.title,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                sinopsis=story.sinopsis,
                atmosfera=story.atmosfera,
                num_beats=num_beats,
            )

        return f"""Crea una escaleta de {num_beats} beats para esta historia de terror:

Título: {story.title}
Protagonistas: {story.protagonista}
Escenarios: {story.escenarios}
Sinopsis: {story.sinopsis}
Atmósfera: {story.atmosfera}

Cada beat debe ser un momento clave de la historia.
Responde solo con una lista numerada de beats, cada uno en una línea.
"""

    def build_beat_prompt(self, story: Story, beat: Beat, previous_content: str = "") -> str:
        """Build el prompt para narrar un beat."""
        base = f"""NARRA EL BEAT #{beat.number}:
{beat.summary}

Contexto:
- Protagonistas: {story.protagonista}
- Escenario: {story.escenarios}
- Atmósfera: {story.atmosfera}

Extiende este momento (150-300 palabras)."""

        if previous_content:
            base += f"\n\nLo que pasó antes:\n{previous_content}"

        return base

    def build_voice_prompt(self, story: Story) -> str:
        """Build el system prompt para la Voz."""
        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"

        return f"""Eres la Voz narrativa de una historia de terror.
Tu estilo: {story.atmosfera}
El relator: {story.relator}

REGLAS:
{reglas_str}

Instrucciones:
- Escribe en primera persona
- Usa lenguaje natural, no formal
- Extiende cada momento (150-300 palabras)
- Siente los detalles: sonidos, olores, texturas
- Mantén la tensión y el misterio"""
