"""VozUseCase - genera prosa para un beat."""

import logging
from typing import Optional

from src.application.services import MemoryJournalist, PromptBuilder
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.services.narrator_retry_generator import NarratorRetryGenerator
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, BeatStatus, MacroBeat, NarrativeJournal, Story
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
        debug_collector: DebugCollector | None = None,
        retry_generator: NarratorRetryGenerator | None = None,
    ):
        self.llm = llm
        self.memory_journalist = memory_journalist or MemoryJournalist(llm)
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()
        self.retry_generator = retry_generator or NarratorRetryGenerator(llm)

    async def execute(
        self,
        story: Story,
        beat: Beat,
        previous_beats: list[Beat] | None = None,
        journal: Optional[NarrativeJournal] = None,
    ) -> tuple[Beat, NarrativeJournal, float]:
        """Ejecuta el caso de uso."""
        role_cfg = settings.role_config("voz")
        model = role_cfg.get("model", "mistral:latest")
        temp = float(role_cfg.get("temperature", 0.6))

        previous_beats = previous_beats or []
        if journal is None:
            journal = NarrativeJournal()

        total_beats = story.beat_count() if story.has_beats() else self.prompt_builder.num_beats

        variant = self.prompt_builder.get_variant_name()
        if variant == "compact":
            system_prompt = self.prompt_builder.build_voice_system_compact(story, beat.number)
        else:
            system_prompt = self.prompt_builder.build_voice_prompt(story)

        prompt = self.prompt_builder.build_beat_prompt(
            story=story,
            beat=beat,
            previous_beats=previous_beats,
            journal=journal,
            total_beats=total_beats,
        )

        logger.debug(
            f"[VOZ] beat={beat.number}/{total_beats} model={model} variant={variant} "
            f"system={'None' if system_prompt is None else 'set'} "
            f'summary="{beat.summary[:80]}"'
        )

        response = await self.retry_generator.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temp,
        )

        clean_text = self.normalizer.normalize(response.text, model_name=model)
        logger.debug(f"[VOZ] beat={beat.number} normalized={len(clean_text)} chars")

        role_cfg = settings.role_config("voz")
        self.debug_collector.record(
            role="voz",
            beat_number=beat.number,
            source_component=DebugCollector.source_label(self),
            model=model,
            temperature=temp,
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
            system_prompt=system_prompt,
            user_prompt=prompt,
            raw_response=response.text,
            normalized_response=clean_text,
            parser_result="n/a",
            elapsed_s=response.elapsed_s,
            system_prompt_file="voice_system_compact.md" if variant == "compact" else None,
            user_prompt_file="voice_compact.md" if variant == "compact" else "voice.md",
        )

        beat.system_prompt = system_prompt
        beat.generated_act = clean_text
        beat.status = BeatStatus.COMPLETED

        updated_journal = await self.memory_journalist.update_journal(story, beat, journal)

        return beat, updated_journal, response.elapsed_s

    async def narrate(self, macro_beat: MacroBeat, story: Story) -> tuple[MacroBeat, float]:
        """Narra un macro-beat que ya tiene user_prompt pre-ensamblado (Spec-038).

        Usa build_voz_user_prompt() en lugar de build_beat_prompt(). No toca el journal.
        """
        role_cfg = settings.role_config("voz")
        model = role_cfg.get("model", "mistral:latest")
        temp = float(role_cfg.get("temperature", 0.6))

        variant = self.prompt_builder.get_variant_name()
        if variant == "compact":
            system_prompt = self.prompt_builder.build_voice_system_compact(
                story, beat_number=macro_beat.number, active_rules=macro_beat.active_rules
            )
        else:
            system_prompt = self.prompt_builder.build_voice_prompt(story)

        prompt = self.prompt_builder.build_voz_user_prompt(macro_beat)

        logger.debug(
            f"[VOZ] narrate beat={macro_beat.number} model={model} "
            f"nc={len(macro_beat.user_prompt or '')} chars"
        )

        response = await self.retry_generator.generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temp,
        )

        clean_text = self.normalizer.normalize(response.text, model_name=model)
        macro_beat.system_prompt = system_prompt
        macro_beat.generated_act = clean_text
        macro_beat.status = BeatStatus.COMPLETED

        self.debug_collector.record(
            role="voz",
            beat_number=macro_beat.number,
            source_component=DebugCollector.source_label(self),
            model=model,
            temperature=temp,
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
            system_prompt=system_prompt,
            user_prompt=prompt,
            raw_response=response.text,
            normalized_response=clean_text,
            parser_result="n/a",
            elapsed_s=response.elapsed_s,
            narrative_context=macro_beat.user_prompt,
            system_prompt_file="voice_system_compact.md" if variant == "compact" else None,
            user_prompt_file="(narrative_context inline)",
        )

        return macro_beat, response.elapsed_s
