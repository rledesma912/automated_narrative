"""ScenarioResolverService — distribuye escenarios a cada macro-beat (SPEC-410).

Distribución DETERMINÍSTICA: cada beat recibe un escenario según su posición
en la lista (order_index). Ya no se llama al LLM.
"""

import logging
from typing import TYPE_CHECKING

from src.application.services.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from src.domain.models import Story

logger = logging.getLogger(__name__)


class ScenarioResolverService:
    """Distribuye escenarios a cada macro-beat de forma determinística."""

    def __init__(self, prompt_builder: "PromptBuilder"):
        self.prompt_builder = prompt_builder

    def resolve_distribution(self, story: "Story") -> dict:
        scenarios = story.scenarios or []
        num_beats = self.prompt_builder.num_beats

        if not scenarios:
            return {str(i): {"scenario_index": None} for i in range(1, num_beats + 1)}

        distribution = {}
        for i in range(1, num_beats + 1):
            scenario_idx = min(i - 1, len(scenarios) - 1)
            distribution[str(i)] = {"scenario_index": scenario_idx}

        return distribution
