"""NarrateBeatUseCase - genera prosa para un beat."""

from typing import Optional

from src.config import settings
from src.domain.models import Beat, NarrativeJournal, Story
from src.domain.interfaces import LLMProvider
from src.application.services import MemoryJournalist, PromptBuilder


class NarrateBeatUseCase:
    """Caso de uso para narrar un beat (Voz)."""

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
    ) -> tuple[Beat, NarrativeJournal]:
        """Ejecuta el caso de uso."""
        model = settings.llm_model
        temp = settings.llm_model_temperature

        previous_content = self._build_previous_context(previous_beats)

        prompt = self.prompt_builder.build_beat_prompt(story, beat, previous_content)

        if journal and journal.last_events:
            prompt = self._inject_journal(prompt, journal)

        system_prompt = self.prompt_builder.build_voice_prompt(story)

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temp,
        )

        beat.content = response.text.strip()
        beat.status = "completed"

        updated_journal = await self.memory_journalist.update_journal(
            story, beat, journal
        )

        return beat, updated_journal

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
