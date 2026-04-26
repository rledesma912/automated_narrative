"""SynopsisBeatMapper - mapea la sinopsis a beats estructurales de forma extractiva."""

import logging

from src.application.services.beat_parser import parse_beats
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import Beat, MacroBeat, Story
from src.infrastructure.normalizers import ResponseNormalizer
from src.infrastructure.parsers.beat_response_parser import BeatResponseParser

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
        beat_parser: BeatResponseParser | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer or ResponseNormalizer()
        self.debug_collector = debug_collector or NullDebugCollector()
        self.beat_parser = beat_parser or BeatResponseParser()

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

        variant = self.prompt_builder._get_prompt_variant()
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
            system_prompt_file="synopsis_mapper_system_compact.md",
            user_prompt_file="synopsis_mapper_compact.md" if variant == "compact" else "synopsis_mapper.md",
        )

        logger.debug(f"[MAPPER] beats mapeados: {[b.summary[:70] for b in beats]}")
        return beats

    async def map_one(
        self,
        story: Story,
        macro_beat_id: int,
        beat_anchors: dict,
        prev_snapshot: str | None = None,
        synopsis_slice: str | None = None,
        active_rules: list[str] | None = None,
        active_scenario_description: str | None = None,
        beat_intent: str | None = None,
        beat_type: str | None = None,
        beat_intensity: str | None = None,
        atmosphere: str | None = None,
    ) -> MacroBeat:
        """Mapea un único macro-beat enriquecido: extrae eventos e integra reglas/escenario.

        El escenario activo se almacena en active_scenario_id como nombre de texto.
        """
        role_cfg = settings.role_config("director")
        model = role_cfg.get("model") or settings.llm_model
        temperature = role_cfg.get("temperature", 0.3)

        prompt = self.prompt_builder.build_synopsis_mapper_one_prompt(
            story=story,
            macro_beat_id=macro_beat_id,
            beat_anchors=beat_anchors,
            prev_snapshot=prev_snapshot,
            synopsis_slice=synopsis_slice,
            active_rules=active_rules,
            active_scenario=active_scenario_description,
            beat_intent=beat_intent,
            beat_type=beat_type,
            beat_intensity=beat_intensity,
            atmosphere=atmosphere,
        )
        system_prompt = self.prompt_builder.build_synopsis_mapper_system(story)

        logger.debug(
            f"[MAPPER] map_one beat={macro_beat_id} model={model} "
            f"rules={len(active_rules or [])} scenario={bool(active_scenario_description)}"
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            role="director",
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
        )

        clean_text = self.normalizer.normalize(response.text, model_name=model)

        summary, active_scenario_from_llm = self.beat_parser.parse_map_one_response(
            clean_text, macro_beat_id, []
        )

        final_scenario = active_scenario_from_llm or active_scenario_description

        macro_beat = MacroBeat(
            number=macro_beat_id,
            summary=summary,
            status="pending",
            active_scenario_id=final_scenario,
            active_scenario_description=active_scenario_description or "",
            active_rules=active_rules or [],
        )

        self.debug_collector.record(
            role="mapper",
            beat_number=macro_beat_id,
            source_component=DebugCollector.source_label(self),
            model=model,
            temperature=temperature,
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
            system_prompt=system_prompt,
            user_prompt=prompt,
            raw_response=response.text,
            normalized_response=clean_text,
            parser_result=f"ok: escenario={active_scenario_from_llm!r}, summary={len(summary)} chars",
            elapsed_s=response.elapsed_s,
            system_prompt_file="synopsis_mapper_system_compact.md",
            user_prompt_file="synopsis_mapper_one_compact.md",
        )

        logger.debug(
            f"[MAPPER] beat #{macro_beat_id} → escenario={active_scenario_from_llm!r} "
            f"summary={summary[:80]}"
        )
        return macro_beat

