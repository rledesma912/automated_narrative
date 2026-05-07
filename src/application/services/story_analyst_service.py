"""StoryAnalystService — extrae NarrativeAnchors de la sinopsis (Spec-081 + Spec-170)."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from src.config import settings
from src.domain.exceptions import NarrativeLiteracyError
from src.domain.interfaces import INarrativeValidator, LLMProvider
from src.domain.models import NarrativeAnchors
from src.infrastructure.normalizers.response_normalizer import ResponseNormalizer

if TYPE_CHECKING:
    from src.application.services.debug_collector import DebugCollector
    from src.application.services.prompt_builder import PromptBuilder
    from src.domain.models import Story

logger = logging.getLogger(__name__)


def _load_pillars() -> list[dict]:
    """Carga los pilares de resonancia desde config/llm_narrative_definition.yaml."""
    yaml_path = Path("config/llm_narrative_definition.yaml")
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("resonance_pillars", [])


@dataclass
class _ExtractionResult:
    anchors: NarrativeAnchors
    raw: str
    normalized: str


class StoryAnalystService:
    """Extrae anclajes narrativos de la sinopsis y los resuelve por macro-beat.

    Responsabilidades:
    1. extract_anchors(story)           — LLM: sinopsis → NarrativeAnchors (5 pilares)
    2. resolve_beat_anchors(anchors, n) — 1:1 mapping: Beat N → resonancia N (sin LLM)

    Con auditor inyectado (Spec-170):
    - assertive: intenta con prompt corto; si falla auditoría → NarrativeLiteracyError
    - auto: intenta assertive; si falla → reintenta con descriptive
    - descriptive: usa prompt descriptivo directamente, sin auditoría
    """

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: "PromptBuilder",
        normalizer=None,
        debug_collector: "DebugCollector | None" = None,
        auditor: "INarrativeValidator | None" = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = (
            normalizer if normalizer is not None else ResponseNormalizer(role="story_analyst")
        )
        self._debug = debug_collector
        self._auditor = auditor
        self._pillars = _load_pillars()
        self._anchor_keys = [p["field"] for p in self._pillars]

    async def extract_anchors(self, story: "Story") -> NarrativeAnchors:
        """Extrae los 5 anclajes de resonancia narrativa de la sinopsis.

        Aplica el ciclo assertive → auditoría → reintento según la estrategia activa.
        Si no hay auditor inyectado, el comportamiento es idéntico al original.
        """
        if not self._auditor:
            result = await self._attempt_extract(story, use_assertive=False)
            self._record_debug(story, result, use_assertive=False)
            return result.anchors

        strategy = settings.effective_prompting_strategy

        if strategy == "descriptive":
            result = await self._attempt_extract(story, use_assertive=False)
            self._record_debug(story, result, use_assertive=False)
            return result.anchors

        # assertive o auto: primer intento con prompt corto
        result = await self._attempt_extract(story, use_assertive=True)
        self._record_debug(story, result, use_assertive=True)

        audit = self._auditor.validate(result.normalized, story.sinopsis)
        if audit.passed:
            logger.debug("[ANALYST] Auditoría OK (score=%.2f)", audit.score)
            return result.anchors

        logger.warning("[ANALYST] Auditoría fallida — %s (score=%.2f)", audit.reason, audit.score)

        if strategy == "assertive":
            raise NarrativeLiteracyError(audit.reason)

        # auto: reintento con prompt descriptivo
        logger.info("[ANALYST] Modo auto — reintentando con prompt descriptivo")
        result2 = await self._attempt_extract(story, use_assertive=False)
        self._record_debug(story, result2, use_assertive=False)
        return result2.anchors

    # ── extracción interna ───────────────────────────────────────────────────

    async def _attempt_extract(self, story: "Story", use_assertive: bool) -> _ExtractionResult:
        """Llama al LLM y retorna anchors + texto crudo para auditoría."""
        role_cfg = settings.role_config("story_analyst")
        model = role_cfg.get("model", "mistral:latest")
        temperature = role_cfg.get("temperature", 0.3)

        prompt = self.prompt_builder.build_story_analyst_prompt(story)
        system_prompt = self.prompt_builder.build_story_analyst_system(assertive=use_assertive)

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
        normalized = (
            self.normalizer.normalize(raw, model_name=model).strip()
            if self.normalizer
            else raw.strip()
        )

        anchors = self._parse_anchors(normalized, story)
        return _ExtractionResult(anchors=anchors, raw=raw, normalized=normalized)

    def _record_debug(self, story: "Story", result: _ExtractionResult, use_assertive: bool) -> None:
        if not self._debug:
            return
        role_cfg = settings.role_config("story_analyst")
        model = role_cfg.get("model", "mistral:latest")
        temperature = role_cfg.get("temperature", 0.3)
        variant = self.prompt_builder.get_variant_name()

        fields_ok = sum(1 for k in self._anchor_keys if getattr(result.anchors, k, ""))
        system_file = (
            "story_analyst_system_assertive.md"
            if use_assertive
            else "story_analyst_system_compact.md"
        )
        self._debug.record(
            role="story_analyst",
            beat_number=None,
            source_component=type(self).__name__,
            model=model,
            temperature=temperature,
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=role_cfg.get("num_predict"),
            system_prompt=self.prompt_builder.build_story_analyst_system(assertive=use_assertive),
            user_prompt=self.prompt_builder.build_story_analyst_prompt(story),
            raw_response=result.raw,
            normalized_response=result.normalized,
            parser_result=f"OK: {fields_ok} anclajes",
            elapsed_s=0.0,
            system_prompt_file=system_file,
            user_prompt_file="story_analyst_compact.md"
            if variant == "compact"
            else "story_analyst.md",
        )

        logger.debug(
            "[ANALYST] Anclajes extraídos — %s",
            ", ".join(
                f"{k}={len(getattr(result.anchors, k, ''))} chars" for k in self._anchor_keys
            ),
        )

    def resolve_beat_anchors(self, anchors: NarrativeAnchors, beat_id: int) -> dict:
        """Mapeo 1:1: Beat N → resonancia N definida en llm_narrative_definition.yaml."""
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
