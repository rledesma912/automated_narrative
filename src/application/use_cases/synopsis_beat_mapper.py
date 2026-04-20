"""SynopsisBeatMapper - mapea la sinopsis a beats estructurales de forma extractiva."""

import logging

from src.application.services.beat_parser import parse_beats
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, Story
from src.infrastructure.normalizers import ResponseNormalizer

logger = logging.getLogger(__name__)


class SynopsisBeatMapper:
    """Mapea la sinopsis a beats estructurales de forma extractiva.

    Reemplaza a DirectorUseCase en el pipeline de planificación. En lugar de
    generar beats creativamente, extrae de la sinopsis qué ocurre en cada momento
    narrativo definido en llm_beats_definition.yaml.
    """

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder,
        normalizer: ResponseNormalizer | None = None,
        debug_collector: DebugCollector | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()

    async def map(self, story: Story, narrative_brief: str = "") -> list[Beat]:
        """Genera los beats mapeando la sinopsis a la estructura de actos."""
        num_beats = self.prompt_builder.num_beats
        role_cfg = settings.role_config("director")
        model = role_cfg.get("model") or settings.llm_model
        temperature = role_cfg.get("temperature", 0.3)

        variant = self.prompt_builder._get_prompt_variant()
        prompt = self.prompt_builder.build_synopsis_mapper_prompt(story, narrative_brief)
        system_prompt = self.prompt_builder.build_synopsis_mapper_system(story)

        logger.debug(
            f"[MAPPER] model={model} variant={variant} temp={temperature} "
            f"num_beats={num_beats} system={'None' if system_prompt is None else 'set'}"
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            role="director",
        )

        clean_text = self.normalizer.normalize(response.text, model_name=model)
        beats = parse_beats(clean_text, num_beats, story.id, caller="MAPPER")

        self.debug_collector.record(
            role="mapper",
            beat_number=None,
            source_component=DebugCollector.source_label(self),
            model=model,
            temperature=temperature,
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
            system_prompt=system_prompt,
            user_prompt=prompt,
            raw_response=response.text,
            normalized_response=clean_text,
            parser_result=f"ok: {len(beats)} beats" if beats else "error: 0 beats",
            elapsed_s=response.elapsed_s,
        )

        logger.debug(f"[MAPPER] beats mapeados: {[b.summary[:70] for b in beats]}")
        return beats
