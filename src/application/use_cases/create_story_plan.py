"""CreateStoryPlanUseCase - genera la escaleta de beats."""

from src.domain.models import Story, Beat, StoryPlan
from src.domain.interfaces import LLMProvider
from src.application.services import PromptBuilder


class CreateStoryPlanUseCase:
    """Caso de uso para generar el plan de beats (Director)."""

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

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model="qwen3.5:9b",
            temperature=0.4,
        )

        beats = self._parse_beats(response.text, story.id)

        return StoryPlan(
            story_id=story.id,
            title=story.title,
            beats=beats,
        )

    def _parse_beats(self, text: str, story_id) -> list[Beat]:
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
                Beat(number=i, summary="Beat generated", status="pending")
                for i in range(1, 9)
            ]

        return beats
