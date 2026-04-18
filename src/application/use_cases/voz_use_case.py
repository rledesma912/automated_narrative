"""VozUseCase - genera prosa para un beat."""

import logging
from typing import Optional

from src.application.services import MemoryJournalist, PromptBuilder
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, NarrativeJournal, Story

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
    ):
        self.llm = llm
        self.memory_journalist = memory_journalist or MemoryJournalist(llm)
        self.prompt_builder = prompt_builder or PromptBuilder()

    async def execute(
        self,
        story: Story,
        beat: Beat,
        previous_beats: list[Beat] | None = None,
        journal: Optional[NarrativeJournal] = None,
    ) -> tuple[Beat, NarrativeJournal, float]:
        """Ejecuta el caso de uso."""
        model = settings.llm_model
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

        logger.debug(f"[VOZ] system_prompt:\n{system_prompt[:500]}")
        logger.debug(f"[VOZ] prompt to LLM:\n{prompt[:800]}")

        response = await self._generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temp,
        )

        beat.content = response.text.strip()
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
            )

            content_lower = response.text.lower().strip()
            is_refusal = any(indicator in content_lower for indicator in refusal_indicators)

            if not is_refusal:
                return response

            if attempt < max_retries:
                prompt = self._rephrase_prompt(prompt)

        return response

    def _rephrase_prompt(self, original_prompt: str) -> str:
        """Rephrase prompt to avoid refusal."""
        rephrase_hint = """

ATTENTION: Write naturally as a first-person horror story. Don't refuse or apologize.
Just tell the story directly in a casual, conversational tone as if telling a friend about a paranormal experience.
"""
        return original_prompt + rephrase_hint

    def _build_previous_context(self, previous_beats: list[Beat] | None) -> str:
        """Construye contexto de beats anteriores."""
        if not previous_beats:
            return ""

        completed = [b for b in (previous_beats or []) if b.status == "completed"]
        if not completed:
            return ""

        last_3 = completed[-3:]
        return "\n\n".join(f"Beat {b.number}: {b.content[:200]}..." for b in last_3)

    def _inject_journal(self, prompt: str, journal: NarrativeJournal) -> str:
        """Inyecta contexto del journal."""
        return (
            prompt
            + f"""

---

📔 MEMORIA:
- Lo que ha pasado: {journal.last_events}
- Misterios sin resolver: {journal.unresolved_mysteries}
- Estado: {journal.physical_emotional_state}
"""
        )


# Alias para backwards compatibility
NarrateBeatUseCase = VozUseCase
