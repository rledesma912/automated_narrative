"""MemoryJournalist - gestiona la coherencia narrativa."""

import json
from typing import Optional

from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.services.prompt_builder import PromptBuilder
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, MacroBeat, NarrativeJournal, Story


class MemoryJournalist:
    """Gestiona la memoria narrativa entre beats."""

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder | None = None,
        debug_collector: DebugCollector | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder or PromptBuilder()
        self._system_prompt_cache = None
        self.debug_collector = debug_collector or NullDebugCollector()

    async def update_journal(
        self,
        story: Story,
        beat: Beat,
        previous_journal: Optional[NarrativeJournal] = None,
    ) -> NarrativeJournal:
        """Actualiza el journal después de un beat."""
        prompt = self.prompt_builder.build_journal_prompt(story, beat, previous_journal)
        system_prompt = self._get_system_prompt()

        from src.config import settings

        model = settings.state_extractor_model
        temperature = settings.state_extractor_temperature
        role_cfg = settings.role_config("journal")

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
        )

        normalized = response.text.strip()
        self.debug_collector.record(
            role="journal",
            beat_number=beat.number,
            source_component=DebugCollector.source_label(self),
            model=model,
            temperature=temperature,
            num_ctx=role_cfg.get("num_ctx") if role_cfg else None,
            num_predict=role_cfg.get("num_predict") if role_cfg else None,
            system_prompt=system_prompt,
            user_prompt=prompt,
            raw_response=response.text,
            normalized_response=normalized,
            parser_result="n/a (JSON interno)",
            elapsed_s=response.elapsed_s,
            system_prompt_file=None,
            user_prompt_file="journal.md",
        )

        return self._parse_journal(response.text, previous_journal)

    async def extract(
        self,
        story: Story,
        macro_beat: MacroBeat,
        previous_journal: NarrativeJournal | None = None,
    ) -> tuple[str, NarrativeJournal]:
        """Extrae memory_snapshot (JSON str) y journal actualizado para un macro-beat.

        Retorna (snapshot_json, journal). El snapshot se almacena en MacroBeat.memory_snapshot
        y se pasa como prev_snapshot al build_narrative_context() del siguiente beat.
        """
        journal = await self.update_journal(story, macro_beat, previous_journal)
        snapshot = json.dumps(
            {
                "last_events": journal.last_events,
                "unresolved_mysteries": journal.unresolved_mysteries,
                "physical_emotional_state": journal.physical_emotional_state,
            },
            ensure_ascii=False,
        )
        return snapshot, journal

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
