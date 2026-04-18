"""VozUseCase - genera prosa para un beat."""

import logging
from typing import Optional

from src.application.services import MemoryJournalist, PromptBuilder
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, NarrativeJournal, Story
from src.infrastructure.normalizers import ResponseNormalizer

logger = logging.getLogger(__name__)


class VozUseCase:
    """Caso de uso para narrar un beat (Voz).

    Ejecución narrativa. Transforma el beat en prosa rica y atmosférica.
    """

    def __init__(
        self,
        llm: LLMProvider,
        memory_journalist: Optional[MemoryJournalist] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        normalizer: ResponseNormalizer | None = None,
    ):
        self.llm = llm
        self.memory_journalist = memory_journalist or MemoryJournalist(llm)
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.normalizer = normalizer or ResponseNormalizer()

    async def execute(
        self,
        story: Story,
        beat: Beat,
        previous_beats: list[Beat] | None = None,
        journal: Optional[NarrativeJournal] = None,
    ) -> tuple[Beat, NarrativeJournal, float]:
        """Ejecuta el caso de uso."""
        role_cfg = settings.role_config("voz")
        model = role_cfg.get("model") or settings.llm_model
        temp = settings.voz_temperature

        previous_beats = previous_beats or []
        if journal is None:
            journal = NarrativeJournal()

        total_beats = len(story.beats) if story.beats else self.prompt_builder.num_beats

        logger.debug(f"[VOZ] beat #{beat.number}/{total_beats}, relator={story.relator}")

        prompt = self.prompt_builder.build_beat_prompt(
            story=story,
            beat=beat,
            previous_beats=previous_beats,
            journal=journal,
            total_beats=total_beats,
        )

        system_prompt = self.prompt_builder.build_voice_prompt(story)

        logger.debug(f"[VOZ] ===SYSTEM_PROMPT===\n{system_prompt}\n===END===")
        logger.debug(f"[VOZ] ===BEAT_PROMPT===\n{prompt}\n===END===")

        response = await self._generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temp,
        )

        logger.debug(f"[VOZ] ===RAW_RESPONSE beat#{beat.number}===\n{response.text}\n===END===")

        clean_text = self.normalizer.normalize(response.text, model_name=model)
        beat.content = clean_text
        beat.status = "completed"

        updated_journal = await self.memory_journalist.update_journal(story, beat, journal)

        return beat, updated_journal, response.elapsed_s

    async def _generate_with_retry(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_retries: int = 2,
    ):
        """Genera contenido con retry para manejar refusals."""
        refusal_indicators = ["lo siento", "no puedo", "no puedo cumplir", "no es apropiado"]

        for attempt in range(max_retries + 1):
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                role="voz",
            )

            content_lower = response.text.lower().strip()
            is_refusal = any(indicator in content_lower for indicator in refusal_indicators)

            if not is_refusal:
                return response

            if attempt < max_retries:
                prompt = self._rephrase_prompt(prompt)

        return response

    def _rephrase_prompt(self, original_prompt: str) -> str:
        rephrase_hint = (
            "\n\nATTENTION: Write naturally as a first-person horror story. "
            "Don't refuse or apologize. Just tell the story directly."
        )
        return original_prompt + rephrase_hint


# Alias para backwards compatibility
NarrateBeatUseCase = VozUseCase
