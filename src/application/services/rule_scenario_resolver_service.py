"""RuleScenarioResolverService — distribuye reglas y escenarios detallados (SPEC-041)."""

import json
import logging
from typing import TYPE_CHECKING

from src.config import settings
from src.domain.interfaces import LLMProvider

if TYPE_CHECKING:
    from src.application.services.debug_collector import DebugCollector
    from src.application.services.prompt_builder import PromptBuilder
    from src.domain.models import NarrativeAnchors, Story

logger = logging.getLogger(__name__)


class RuleScenarioResolverService:
    """Asigna reglas y escenarios detallados a cada macro-beat."""

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: "PromptBuilder",
        normalizer=None,
        debug_collector: "DebugCollector | None" = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer
        self._debug = debug_collector

    async def resolve_distribution(
        self, story: "Story", anchors: "NarrativeAnchors | None" = None
    ) -> dict:
        """Llama al LLM para obtener el mapa de distribución de reglas y escenarios."""
        role_cfg = settings.role_config("director")
        model = role_cfg.get("model", "mistral:latest")
        temperature = role_cfg.get("temperature", 0.2)

        prompt = self.prompt_builder.build_rule_resolver_prompt(story, anchors=anchors)
        system_prompt = self.prompt_builder.build_rule_resolver_system()

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            role="director",
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
        )

        raw = response.text
        if self.normalizer:
            normalized = self.normalizer.normalize(raw, model_name=model).strip()
        else:
            normalized = raw.strip()

        distribution = self._parse_distribution(normalized, story)

        if self._debug:
            self._debug.record(
                role="rule_resolver",
                beat_number=None,
                source_component="RuleScenarioResolverService",
                model=model,
                temperature=temperature,
                num_ctx=role_cfg.get("num_ctx"),
                num_predict=role_cfg.get("num_predict"),
                system_prompt=system_prompt,
                user_prompt=prompt,
                raw_response=raw,
                normalized_response=normalized,
                parser_result=f"OK: {len(distribution)} actos mapeados",
                elapsed_s=response.elapsed_s,
                system_prompt_file="rule_resolver_system_compact.md",
                user_prompt_file="rule_resolver_compact.md",
            )

        return distribution

    def _parse_distribution(self, text: str, story: "Story") -> dict:
        """Parsea el JSON de la respuesta y normaliza IDs → content/index.

        Soporta dos formatos de respuesta del LLM:
        - Nuevo (compact): {"1": {"rules": ["R1"], "scenario_id": "S2"}}
        - Legado:          {"1": {"rules": ["texto completo"], "scenario_index": 1}}
        """
        try:
            clean_text = text.replace("```json", "").replace("```", "").strip()
            logger.debug(f"[RESOLVER] Intentando parsear: {clean_text[:200]!r}")
            data = json.loads(clean_text)
        except Exception as e:
            logger.warning(
                f"[RESOLVER] Error parseando distribución: {e}. Respuesta: {text[:300]!r}. Usando fallback."
            )
            num_beats = self.prompt_builder.num_beats
            return {str(i): {"rules": [], "scenario_index": 0} for i in range(1, num_beats + 1)}

        # Mapas de normalización
        id_to_content: dict[str, str] = {}
        if story.typed_rules:
            id_to_content = {r.id: r.content for r in story.typed_rules}
        elif story.reglas:
            id_to_content = {str(i + 1): r for i, r in enumerate(story.reglas)}

        scenario_id_to_idx: dict[str, int] = {}
        for i, s in enumerate(story.scenarios or []):
            scenario_id_to_idx[f"S{s.order_index + 1}"] = i
            scenario_id_to_idx[s.name] = i
            scenario_id_to_idx[str(s.id)] = i

        num_scenarios = len(story.scenarios or [])
        num_beats = self.prompt_builder.num_beats

        normalized: dict = {}
        for beat_key, beat_data in data.items():
            if not isinstance(beat_data, dict):
                continue
            rules_raw = beat_data.get("rules", [])
            # ID → content (fallback: mantener string original)
            rules_content = [id_to_content.get(str(r), str(r)) for r in rules_raw]

            # scenario_id (nuevo) o scenario_index (legado)
            scenario_id = beat_data.get("scenario_id", beat_data.get("scenario", ""))
            scenario_index = beat_data.get("scenario_index", None)
            if scenario_id:
                scenario_index = scenario_id_to_idx.get(str(scenario_id), None)

            normalized[beat_key] = {"rules": rules_content, "scenario_index": scenario_index}

        # Fallback: beats sin scenario_index → asignación proporcional por posición
        if num_scenarios > 0:
            for i in range(1, num_beats + 1):
                beat_key = str(i)
                if beat_key not in normalized:
                    normalized[beat_key] = {"rules": [], "scenario_index": None}
                if normalized[beat_key].get("scenario_index") is None:
                    proportional = min(i - 1, num_scenarios - 1)
                    normalized[beat_key]["scenario_index"] = proportional
                    logger.debug(
                        f"[RESOLVER] beat {i} sin escenario asignado → fallback idx={proportional}"
                    )

        return normalized
