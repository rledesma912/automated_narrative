"""StoryAnalystService — extrae NarrativeAnchors de la sinopsis (Spec-038)."""

import logging
import re
from typing import TYPE_CHECKING

from src.config import settings
from src.domain.models import NarrativeAnchors, resolve_beat_anchors
from src.domain.interfaces import LLMProvider
from src.infrastructure.normalizers.response_normalizer import ResponseNormalizer

if TYPE_CHECKING:
    from src.application.services.prompt_builder import PromptBuilder
    from src.application.services.debug_collector import DebugCollector
    from src.domain.models import Story

logger = logging.getLogger(__name__)

_ANCHOR_KEYS = ("initial_state", "threat_nature", "horror_peak", "spatial_anchor")


class StoryAnalystService:
    """Extrae anclajes narrativos de la sinopsis y los resuelve por macro-beat.

    Responsabilidades:
    1. extract_anchors(story)          — LLM: sinopsis → NarrativeAnchors (JSON)
    2. resolve_beat_anchors(anchors, beat_id) — determinístico: delega a domain function
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

    async def extract_anchors(self, story: "Story") -> NarrativeAnchors:
        """Llama al LLM para extraer los 4 anclajes narrativos de la sinopsis.

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
        if self.normalizer:
            normalized = self.normalizer.normalize(raw, model_name=model).strip()
        else:
            normalized = raw.strip()

        anchors = self._parse_anchors(normalized, story)

        if self._debug:
            from src.application.services.debug_collector import DebugCollector
            variant = self.prompt_builder._get_prompt_variant()
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
                parser_result=f"OK: {len([v for v in [anchors.initial_state, anchors.threat_nature, anchors.horror_peak, anchors.spatial_anchor] if v])} anclajes",
                elapsed_s=response.elapsed_s,
                system_prompt_file="story_analyst_system_compact.md",
                user_prompt_file="story_analyst_compact.md" if variant == "compact" else "story_analyst.md",
            )

        logger.debug(
            "[ANALYST] Anclajes extraídos — initial_state=%d chars, threat_nature=%d chars, "
            "horror_peak=%d chars, spatial_anchor=%d chars",
            len(anchors.initial_state), len(anchors.threat_nature),
            len(anchors.horror_peak), len(anchors.spatial_anchor),
        )
        return anchors

    def resolve_beat_anchors(self, anchors: NarrativeAnchors, macro_beat_id: int) -> dict:
        """Retorna los anclajes principal y contexto para un macro-beat según el YAML."""
        return resolve_beat_anchors(anchors, macro_beat_id, self.prompt_builder._beats_spec)

    # ── parsing ──────────────────────────────────────────────────────────────

    def _parse_anchors(self, text: str, story: "Story") -> NarrativeAnchors:
        """Parsea secciones ## key del texto. Aplica fallback si faltan campos."""
        data = self._extract_sections(text)
        if data and all(k in data for k in _ANCHOR_KEYS):
            return NarrativeAnchors(
                story_id=story.id,
                initial_state=data["initial_state"],
                threat_nature=data["threat_nature"],
                horror_peak=data["horror_peak"],
                spatial_anchor=data["spatial_anchor"],
            )

        logger.warning("[ANALYST] Secciones incompletas o ausentes — aplicando fallback")
        return self._fallback_anchors(text, story)

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

    def _fallback_anchors(self, text: str, story: "Story") -> NarrativeAnchors:
        """Fallback: rellena campos ausentes con fragmento de sinopsis."""
        existing = self._extract_sections(text) or {}
        synopsis_snippet = story.sinopsis[:120] if story.sinopsis else "N/D"
        return NarrativeAnchors(
            story_id=story.id,
            initial_state=existing.get("initial_state") or synopsis_snippet,
            threat_nature=existing.get("threat_nature") or synopsis_snippet,
            horror_peak=existing.get("horror_peak") or synopsis_snippet,
            spatial_anchor=existing.get("spatial_anchor") or synopsis_snippet,
        )
