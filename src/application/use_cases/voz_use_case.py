"""VozUseCase - escribe la prosa de un acto (Spec-530 S7: prompts armados desde la escaleta)."""

import logging

from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.services.narrator_retry_generator import NarratorRetryGenerator
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import BeatStatus, MacroBeat
from src.infrastructure.normalizers import ResponseNormalizer

logger = logging.getLogger(__name__)


class VozUseCase:
    """La Voz: recibe los prompts del acto (OutlineNarrator) y devuelve la prosa limpia."""

    def __init__(
        self,
        llm: LLMProvider,
        normalizer: ResponseNormalizer | None = None,
        debug_collector: DebugCollector | None = None,
        retry_generator: NarratorRetryGenerator | None = None,
    ):
        self.llm = llm
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()
        self.retry_generator = retry_generator or NarratorRetryGenerator(llm)

    async def narrate_with_prompts(
        self, macro_beat: MacroBeat, system_prompt: str, prompt: str
    ) -> tuple[MacroBeat, float]:
        """Narra un acto con prompts ya armados."""
        role_cfg = settings.role_config("voz")
        model = role_cfg.get("model", "mistral:latest")
        temp = float(role_cfg.get("temperature", 0.6))
        response = await self.retry_generator.generate_with_retry(
            prompt=prompt, system_prompt=system_prompt, model=model, temperature=temp
        )
        clean_text = self.normalizer.normalize(response.text, model_name=model)
        macro_beat.system_prompt = system_prompt
        macro_beat.user_prompt = prompt
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
            system_prompt_file="outline_voice_system.md",
            user_prompt_file="outline_voice.md",
        )
        return macro_beat, response.elapsed_s
