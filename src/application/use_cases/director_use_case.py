"""DirectorUseCase - genera la escaleta de beats."""

import logging
import re

from src.application.services import PromptBuilder
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, Story, StoryPlan
from src.infrastructure.normalizers import ResponseNormalizer

logger = logging.getLogger(__name__)


class DirectorUseCase:
    """Caso de uso para generar el plan de beats (Director).

    Planificación estructural. Divide la historia en beats lógicos.
    """

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        normalizer: ResponseNormalizer | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer or ResponseNormalizer()

    async def execute(self, story: Story) -> StoryPlan:
        """Genera la escaleta de beats. num_beats viene del YAML via PromptBuilder."""
        num_beats = self.prompt_builder.num_beats
        prompt = self.prompt_builder.build_planner_prompt(story)
        system_prompt = self.prompt_builder.build_system_prompt(story)

        logger.debug(f"[DIRECTOR] ===SYSTEM_PROMPT===\n{system_prompt}\n===END===")
        logger.debug(f"[DIRECTOR] ===PLANNER_PROMPT===\n{prompt}\n===END===")

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=settings.role_config("director").get("model"),
            temperature=settings.director_temperature,
            role="director",
        )

        logger.debug(f"[DIRECTOR] ===RAW_RESPONSE===\n{response.text}\n===END===")

        clean_text = self.normalizer.normalize(response.text, model_name=settings.llm_model)
        beats = self._parse_beats(clean_text, story.id, num_beats)

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
            match = re.match(r"^(\d+)", line)
            if match:
                beat_number = int(match.group(1))
                summary = line[len(match.group(0)):].strip(".- ").strip()
                if summary:
                    beats.append(
                        Beat(
                            number=beat_number,
                            summary=summary,
                            status="pending",
                        )
                    )

        if not beats:
            logger.warning(
                f"[DIRECTOR] FALLBACK: no se pudo parsear la respuesta, "
                f"se usan {num_beats} beats genéricos. Raw response:\n{text[:2000]}"
            )
            beats = [
                Beat(number=i, summary=f"Beat #{i} generado automáticamente", status="pending")
                for i in range(1, num_beats + 1)
            ]
        else:
            logger.debug(
                f"[DIRECTOR] {len(beats)} beats parseados OK: "
                f"{[b.summary[:60] for b in beats]}"
            )

        return beats


# Alias para backwards compatibility
CreateStoryPlanUseCase = DirectorUseCase
