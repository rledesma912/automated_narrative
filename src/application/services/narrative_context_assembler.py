"""NarrativeContextAssembler — ensambla el narrative_context para el VOZ."""

import json
import logging

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.domain.models import MacroBeat

logger = logging.getLogger(__name__)


class NarrativeContextAssembler:
    """Ensambla el bloque narrative_context determinístico que recibe el VOZ.

    Spec-081: cada beat recibe una sola resonancia (mapeo 1:1 Beat N → Pilar N).
    El bloque GUÍA DE VOZ usa el label_voz del pilar como etiqueta semántica.
    """

    def __init__(self, beat_repo: BeatSpecRepository) -> None:
        self._beat_repo = beat_repo

    def assemble(
        self,
        macro_beat: MacroBeat,
        beat_anchors: dict,
        prev_snapshot: str | None = None,
        cast_block: str | None = None,
    ) -> str:
        """Combina beat_spec + resonancia + evento + escenario + memoria anterior."""
        beat_spec = self._beat_repo.get_by_id(macro_beat.number)
        sc = beat_spec.get("state_change", {})
        must_not_items = beat_spec.get("must_not", [])
        success_items = beat_spec.get("success_signal", [])

        # Los EVENTOS van primero — el LLM presta más atención al inicio del contexto.
        lines = [
            "EVENTO DE ESTE MOMENTO (narrá EXACTAMENTE estos eventos, en orden):",
            macro_beat.summary or "",
        ]

        if cast_block:
            lines += ["", cast_block]

        lines += [
            "",
            "ESCENARIO: " + (macro_beat.active_scenario_id or ""),
            f"ACTO: {beat_spec.get('name', '')} — {beat_spec.get('intent', '')}",
            f"INTENSIDAD: {beat_spec.get('intensity', '')}",
            f"ARCO EMOCIONAL: {sc.get('from', '')} → {sc.get('to', '')}",
        ]

        # Bloque de resonancia: 1 pilar por beat (Spec-081)
        resonance_value = beat_anchors.get("resonance", "")
        resonance_label = beat_anchors.get("label_voz", "RESONANCIA NARRATIVA")
        if resonance_value:
            lines += [
                "",
                "── GUÍA DE VOZ (perspectiva del narrador — NO son eventos adicionales) ──",
                "",
                f"{resonance_label}:",
                resonance_value,
                "── FIN GUÍA DE VOZ ──",
            ]

        if macro_beat.active_rules:
            lines += ["", "REGLAS ESPECÍFICAS PARA ESTE ACTO:"]
            lines.extend([f"- {r}" for r in macro_beat.active_rules])

        if prev_snapshot:
            try:
                data = json.loads(prev_snapshot)
                last_events = data.get("last_events", "")
                phys_state = data.get("physical_emotional_state", "")
                lines += ["", "MEMORIA DEL ACTO ANTERIOR:"]
                if last_events:
                    lines.append(last_events)
                if phys_state:
                    lines.append(f"Estado: {phys_state}")
            except (json.JSONDecodeError, AttributeError):
                lines += ["", "MEMORIA DEL ACTO ANTERIOR:", str(prev_snapshot)]

        lines += [
            "",
            "FIDELIDAD: Narrá SOLO lo que está en EVENTO DE ESTE MOMENTO.",
            "No inventés eventos, objetos, diálogos ni signos específicos que no estén listados.",
            "Si un evento menciona algo vago ('ciertos signos'), narrás la PERCEPCIÓN del narrador, no manifestaciones concretas inventadas.",
            "Los nombres propios de los EVENTOS son exactos: usá esos términos, nunca sinónimos ni variantes.",
            "Los verbos de EVENTO son exactos: 'llega' = llegada física, no despertar; 'sale' = partida; 'sulki' es sulki, no auto. No reformulés.",
            f"PROHIBIDO: {' / '.join(must_not_items)}",
            f"Efecto buscado: {success_items[0] if success_items else ''}",
        ]

        return "\n".join(lines)
