"""RuleScenarioResolverService — distribuye reglas y escenarios detallados (SPEC-041)."""

import json
import logging
from typing import TYPE_CHECKING

from src.config import settings
from src.domain.interfaces import LLMProvider

if TYPE_CHECKING:
    from src.application.services.prompt_builder import PromptBuilder
    from src.application.services.debug_collector import DebugCollector
    from src.domain.models import Story

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

    async def resolve_distribution(self, story: "Story") -> dict:
        """Llama al LLM para obtener el mapa de distribución de reglas y escenarios."""
        role_cfg = settings.role_config("director")
        model = role_cfg.get("model") or settings.llm_model
        temperature = role_cfg.get("temperature", 0.2)

        prompt = self.prompt_builder.build_rule_resolver_prompt(story)
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
        """Parsea el JSON de la respuesta. Fallback a dict vacío por beat si falla."""
        try:
            # Limpiar posibles bloques de código markdown
            clean_text = text.replace("```json", "").replace("```", "").strip()
            logger.debug(f"[RESOLVER] Intentando parsear: {clean_text[:200]!r}", module="resolver", line=1)
            data = json.loads(clean_text)
            return data
        except Exception as e:
            logger.warning(f"[RESOLVER] Error parseando distribución: {e}. Respuesta: {text[:300]!r}. Usando fallback.")
            num_beats = self.prompt_builder.num_beats
            return {str(i): {"rules": [], "scenario_index": 0} for i in range(1, num_beats + 1)}
