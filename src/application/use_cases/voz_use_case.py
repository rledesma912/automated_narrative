"""VozUseCase - genera prosa para un beat."""

import logging
from typing import Optional

from src.application.services import MemoryJournalist, PromptBuilder
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, MacroBeat, NarrativeJournal, Story
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
    ):
        self.llm = llm
        self.memory_journalist = memory_journalist or MemoryJournalist(llm)
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()

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

        variant = self.prompt_builder._get_prompt_variant()
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

        response = await self._generate_with_retry(
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

        beat.content = clean_text
        beat.status = "completed"

        updated_journal = await self.memory_journalist.update_journal(story, beat, journal)

        return beat, updated_journal, response.elapsed_s

    async def narrate(self, macro_beat: MacroBeat, story: Story) -> tuple[MacroBeat, float]:
        """Narra un macro-beat que ya tiene narrative_context pre-ensamblado (Spec-038).

        Usa build_voz_user_prompt() en lugar de build_beat_prompt(). No toca el journal.
        """
        role_cfg = settings.role_config("voz")
        model = role_cfg.get("model") or settings.llm_model
        temp = settings.voz_temperature

        variant = self.prompt_builder._get_prompt_variant()
        if variant == "compact":
            system_prompt = self.prompt_builder.build_voice_system_compact(story)
        else:
            system_prompt = self.prompt_builder.build_voice_prompt(story)

        prompt = self.prompt_builder.build_voz_user_prompt(macro_beat)

        logger.debug(
            f"[VOZ] narrate beat={macro_beat.number} model={model} "
            f'nc={len(macro_beat.narrative_context or "")} chars'
        )

        response = await self._generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temp,
        )

        clean_text = self.normalizer.normalize(response.text, model_name=model)
        macro_beat.content = clean_text
        macro_beat.status = "completed"

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
            narrative_context=macro_beat.narrative_context,
            system_prompt_file="voice_system_compact.md" if variant == "compact" else None,
            user_prompt_file="(narrative_context inline)",
        )

        return macro_beat, response.elapsed_s

    async def _generate_with_retry(
        self,
        prompt: str,
        system_prompt: str | None,
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
