"""StoryAnalystService — extrae NarrativeAnchors de la sinopsis (Spec-081)."""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from src.config import settings
from src.domain.models import NarrativeAnchors
from src.domain.interfaces import LLMProvider
from src.infrastructure.normalizers.response_normalizer import ResponseNormalizer

if TYPE_CHECKING:
    from src.application.services.prompt_builder import PromptBuilder
    from src.application.services.debug_collector import DebugCollector
    from src.domain.models import Story

logger = logging.getLogger(__name__)


def _load_pillars() -> list[dict]:
    """Carga los pilares de resonancia desde config/llm_narrative_definition.yaml."""
    yaml_path = Path("config/llm_narrative_definition.yaml")
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("resonance_pillars", [])


class StoryAnalystService:
    """Extrae anclajes narrativos de la sinopsis y los resuelve por macro-beat.

    Responsabilidades:
    1. extract_anchors(story)           — LLM: sinopsis → NarrativeAnchors (5 pilares)
    2. resolve_beat_anchors(anchors, n) — 1:1 mapping: Beat N → resonancia N (sin LLM)
    """

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: "PromptBuilder",
        normalizer=None,
        debug_collector: "DebugCollector | None" = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer if normalizer is not None else ResponseNormalizer(role="story_analyst")
        self._debug = debug_collector
        self._pillars = _load_pillars()
        self._anchor_keys = [p["field"] for p in self._pillars]

    async def extract_anchors(self, story: "Story") -> NarrativeAnchors:
        """Llama al LLM para extraer los 5 anclajes de resonancia narrativa de la sinopsis.

        Parsea secciones Markdown (## key) y retorna NarrativeAnchors estructurado.
        Si faltan secciones, aplica fallback con fragmento de sinopsis.
        """
        role_cfg = settings.role_config("story_analyst")
        model = role_cfg.get("model") or settings.llm_model
        temperature = role_cfg.get("temperature", 0.3)

        prompt = self.prompt_builder.build_story_analyst_prompt(story)
        system_prompt = self.prompt_builder.build_story_analyst_system()

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            role="story_analyst",
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
        )

        raw = response.text
        normalized = self.normalizer.normalize(raw, model_name=model).strip() if self.normalizer else raw.strip()

        anchors = self._parse_anchors(normalized, story)

        if self._debug:
            from src.application.services.debug_collector import DebugCollector
            variant = self.prompt_builder._get_prompt_variant()
            fields_ok = sum(1 for k in self._anchor_keys if getattr(anchors, k, ""))
            self._debug.record(
                role="story_analyst",
                beat_number=None,
                source_component=DebugCollector.source_label(self),
                model=model,
                temperature=temperature,
                num_ctx=role_cfg.get("num_ctx"),
                num_predict=role_cfg.get("num_predict"),
                system_prompt=system_prompt,
                user_prompt=prompt,
                raw_response=raw,
                normalized_response=normalized,
                parser_result=f"OK: {fields_ok} anclajes",
                elapsed_s=response.elapsed_s,
                system_prompt_file="story_analyst_system_compact.md",
                user_prompt_file="story_analyst_compact.md" if variant == "compact" else "story_analyst.md",
            )

        logger.debug(
            "[ANALYST] Anclajes extraídos — %s",
            ", ".join(f"{k}={len(getattr(anchors, k, ''))} chars" for k in self._anchor_keys),
        )
        return anchors

    def resolve_beat_anchors(self, anchors: NarrativeAnchors, beat_id: int) -> dict:
        """Mapeo 1:1: Beat N → resonancia N definida en llm_narrative_definition.yaml.

        Retorna {"resonance": valor, "label_voz": etiqueta} para el ensamblador.
        """
        for pillar in self._pillars:
            if pillar["beat"] == beat_id:
                field = pillar["field"]
                value = getattr(anchors, field, "")
                return {
                    "resonance": value,
                    "label_voz": pillar.get("label_voz", field),
                }
        return {}

    # ── parsing ──────────────────────────────────────────────────────────────

    def _parse_anchors(self, text: str, story: "Story") -> NarrativeAnchors:
        """Parsea secciones ## key del texto. Aplica fallback si faltan campos."""
        data = self._extract_sections(text)
        if data and all(k in data for k in self._anchor_keys):
            return NarrativeAnchors(story_id=story.id, **{k: data[k] for k in self._anchor_keys})
        logger.warning("[ANALYST] Secciones incompletas o ausentes — aplicando fallback")
        return self._fallback_anchors(data or {}, story)

    def _extract_sections(self, text: str) -> dict | None:
        """Extrae secciones Markdown '## key\\nvalor' del texto."""
        sections: dict[str, str] = {}
        matches = list(re.finditer(r"^##\s*(\w+)", text, re.MULTILINE))
        for i, m in enumerate(matches):
            key = m.group(1).lower()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[key] = text[start:end].strip()
        return sections if sections else None

    def _fallback_anchors(self, existing: dict, story: "Story") -> NarrativeAnchors:
        """Fallback: rellena campos ausentes con fragmento de sinopsis."""
        synopsis_snippet = story.sinopsis[:120] if story.sinopsis else "N/D"
        return NarrativeAnchors(
            story_id=story.id,
            **{k: existing.get(k) or synopsis_snippet for k in self._anchor_keys},
        )
