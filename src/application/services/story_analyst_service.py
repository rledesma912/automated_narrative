"""StoryAnalystService — extrae NarrativeAnchors de la sinopsis (Spec-038)."""

import json
import logging
import re
from typing import TYPE_CHECKING

from src.config import settings
from src.domain.models import NarrativeAnchors, resolve_beat_anchors
from src.domain.interfaces import LLMProvider

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
        self.normalizer = normalizer
        self._debug = debug_collector

    async def extract_anchors(self, story: "Story") -> NarrativeAnchors:
        """Llama al LLM para extraer los 4 anclajes narrativos de la sinopsis.

        Parsea la respuesta JSON y retorna un objeto NarrativeAnchors estructurado.
        Si el LLM devuelve JSON inválido, aplica fallback con texto de la sinopsis.
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
        """Parsea la respuesta del LLM como JSON. Aplica fallback si falla."""
        data = self._extract_json(text)
        if data and all(k in data for k in _ANCHOR_KEYS):
            return NarrativeAnchors(
                story_id=story.id,
                initial_state=str(data["initial_state"]).strip(),
                threat_nature=str(data["threat_nature"]).strip(),
                horror_peak=str(data["horror_peak"]).strip(),
                spatial_anchor=str(data["spatial_anchor"]).strip(),
            )

        logger.warning("[ANALYST] JSON inválido o incompleto — aplicando fallback")
        return self._fallback_anchors(text, story)

    def _extract_json(self, text: str) -> dict | None:
        """Extrae el primer objeto JSON válido del texto, ignorando markdown fences."""
        # Quita bloques de código markdown: ```json ... ``` o ``` ... ```
        clean = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL)
        # Busca el primer { ... } en el texto limpio
        match = re.search(r"\{[^{}]*\}", clean, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    def _fallback_anchors(self, text: str, story: "Story") -> NarrativeAnchors:
        """Fallback: intenta mapear líneas del formato viejo (N. Label: valor)."""
        mapping = {
            "initial_state": ["estado inicial", "1."],
            "threat_nature": ["amenaza", "2."],
            "horror_peak": ["momento clave", "3.", "4."],
            "spatial_anchor": ["escenario", "5."],
        }
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        result: dict[str, str] = {k: "" for k in _ANCHOR_KEYS}

        for line in lines:
            line_lower = line.lower()
            for key, markers in mapping.items():
                if not result[key] and any(line_lower.startswith(m) for m in markers):
                    # Extrae el valor después del primer ":"
                    if ":" in line:
                        result[key] = line.split(":", 1)[1].strip()

        # Último recurso: poner fragmento de sinopsis en campos vacíos
        synopsis_snippet = story.sinopsis[:120] if story.sinopsis else "N/D"
        for k in _ANCHOR_KEYS:
            if not result[k]:
                result[k] = synopsis_snippet

        return NarrativeAnchors(story_id=story.id, **result)
