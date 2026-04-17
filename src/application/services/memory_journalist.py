"""MemoryJournalist - gestiona la coherencia narrativa."""

import json
from typing import TYPE_CHECKING, Optional

from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, NarrativeJournal, Story

if TYPE_CHECKING:
    from src.application.services import PromptBuilder


class MemoryJournalist:
    """Gestiona la memoria narrativa entre beats."""

    def __init__(self, llm: LLMProvider, prompt_builder: "PromptBuilder | None" = None):
        self.llm = llm
        self._prompt_builder = prompt_builder
        self._system_prompt_cache = None

    @property
    def prompt_builder(self) -> "PromptBuilder":
        """Lazy load PromptBuilder."""
        if self._prompt_builder is None:
            from src.application.services import PromptBuilder

            self._prompt_builder = PromptBuilder()
        return self._prompt_builder

    async def update_journal(
        self,
        story: Story,
        beat: Beat,
        previous_journal: Optional[NarrativeJournal] = None,
    ) -> NarrativeJournal:
        """Actualiza el journal después de un beat."""
        prompt = self.prompt_builder.build_journal_prompt(story, beat, previous_journal)

        from src.config import settings

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            model=settings.llm_model,
            temperature=0.3,
        )

        return self._parse_journal(response.text, previous_journal)

    async def summarize_beats(self, completed_beats: list[Beat]) -> str:
        """Resumen conciso de beats para el contexto."""
        if not completed_beats:
            return ""

        last_3 = completed_beats[-3:]
        parts = [f"Beat {b.number}: {b.summary}" for b in last_3]

        if len(completed_beats) > 3:
            parts.insert(0, f"[... {len(completed_beats) - 3} beats anteriores ...]")

        return "\n".join(parts)

    def _parse_journal(self, text: str, previous: Optional[NarrativeJournal]) -> NarrativeJournal:
        """Parsea la respuesta del LLM en journal."""
        try:
            json_match = text.strip().split("{")[-1].split("}")[0]
            data = json.loads("{" + json_match + "}")
            return NarrativeJournal(
                last_events=data.get("last_events", ""),
                unresolved_mysteries=data.get("unresolved_mysteries", ""),
                physical_emotional_state=data.get("physical_emotional_state", ""),
            )
        except (json.JSONDecodeError, ValueError):
            return previous or NarrativeJournal()

    def _get_system_prompt(self) -> str:
        """System prompt para el journalist."""
        if self._system_prompt_cache is None:
            self._system_prompt_cache = (
                "Eres un asistente que genera resúmenes narrativos en JSON. "
                "Solo respondes con JSON válido, sin markdown ni texto adicional."
            )
        return self._system_prompt_cache
