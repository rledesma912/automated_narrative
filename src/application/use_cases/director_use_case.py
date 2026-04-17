"""DirectorUseCase - genera la escaleta de beats."""

from src.application.services import PromptBuilder
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

    async def execute(self, story: Story, num_beats: int = 8) -> StoryPlan:
        """Genera la escaleta de beats."""
        prompt = self.prompt_builder.build_planner_prompt(story, num_beats)
        system_prompt = self.prompt_builder.build_system_prompt(story)

        # Usar modelo None para que el adapter use su valor por defecto
        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=None,
            temperature=0.4,
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

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line and line[0].isdigit():
                summary = line.split(".", 1)[-1].strip() if "." in line else line
                if summary:
                    beats.append(
                        Beat(
                            number=i,
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
