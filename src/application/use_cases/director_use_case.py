"""DirectorUseCase - genera la escaleta de beats."""

import re

from src.application.services import PromptBuilder
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, Story, StoryPlan


class DirectorUseCase:
    """Caso de uso para generar el plan de beats (Director).

    Planificación estructural. Divide la historia en beats lógicos.
    """

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder

    async def execute(self, story: Story) -> StoryPlan:
        """Genera la escaleta de beats. num_beats viene del YAML via PromptBuilder."""
        num_beats = self.prompt_builder.num_beats
        prompt = self.prompt_builder.build_planner_prompt(story)
        system_prompt = self.prompt_builder.build_system_prompt(story)

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=None,
            temperature=settings.director_temperature,
        )

        beats = self._parse_beats(response.text, story.id, num_beats)

        return StoryPlan(
            story_id=story.id,
            title=story.title,
            beats=beats,
        )

    def _parse_beats(self, text: str, story_id, num_beats: int) -> list[Beat]:
        """Parsea la respuesta del LLM en beats."""
        beats = []
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            # Extraer el número del beat (puede ser "1." o "1" al inicio)
            match = re.match(r"^(\d+)", line)
            if match:
                beat_number = int(match.group(1))
                # Extraer el contenido después del número
                summary = line[len(match.group(0)) :].strip(".- ").strip()
                if summary:
                    beats.append(
                        Beat(
                            number=beat_number,
                            summary=summary,
                            status="pending",
                        )
                    )

        if not beats:
            beats = [
                Beat(number=i, summary=f"Beat #{i} generado automáticamente", status="pending")
                for i in range(1, num_beats + 1)
            ]

        return beats


# Alias para backwards compatibility
CreateStoryPlanUseCase = DirectorUseCase
