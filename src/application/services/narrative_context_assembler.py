"""NarrativeContextAssembler — ensambla el narrative_context para el VOZ."""

import logging

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.domain.models import Entity, MacroBeat, NarrativeJournal

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
        previous_journal: NarrativeJournal | None = None,
        cast_block: str | None = None,
        active_rules: list[str] | None = None,
        entities: list[Entity] | None = None,
        narrator: str = "",
    ) -> str:
        """Combina beat_spec + resonancia + evento + escenario + amenaza + memoria anterior.

        Spec-190 §4.4: `active_rules` se deriva determinísticamente (regla global
        o anclada a este acto) y se pasa explícito; ya no se persiste per-beat.
        Spec-450: con entidades, el beat se resuelve con el nivel de la principal y
        la Voz recibe solo la parte de cada ficha que la exposición del acto permite.
        Sin entidades, el texto es idéntico al de antes.
        """
        entities = entities or []
        principal_level = entities[0].reveal_level if entities else None
        beat_spec = self._beat_repo.get_by_id(macro_beat.number, principal_level)
        sc = beat_spec.get("state_change", {})
        must_not_items = beat_spec.get("must_not", [])
        success_items = beat_spec.get("success_signal", [])

        # Los EVENTOS van primero — el LLM presta más atención al inicio del contexto.
        # Spec-470 §1.3: los eventos vienen en tercera persona; el encabezado recuerda
        # quién los cuenta para que no se filtre «Irene no se atreve…».
        persona = f"contalo en primera persona, como {narrator}; " if narrator else ""
        lines = [
            f"EVENTO DE ESTE MOMENTO ({persona}narrá EXACTAMENTE estos eventos, en orden):",
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

        if active_rules:
            lines += ["", "REGLAS ESPECÍFICAS PARA ESTE ACTO:"]
            lines.extend([f"- {r}" for r in active_rules])

        if entities:
            lines += ["", *self._amenaza_block(macro_beat.number, entities)]

        if previous_journal and not previous_journal.is_empty():
            lines += ["", "MEMORIA DEL ACTO ANTERIOR:"]
            if previous_journal.last_events:
                lines.append(previous_journal.last_events)
            if previous_journal.unresolved_mysteries:
                lines.append(f"Misterios sin resolver: {previous_journal.unresolved_mysteries}")
            if previous_journal.physical_emotional_state:
                lines.append(f"Estado: {previous_journal.physical_emotional_state}")
            if entities and previous_journal.entity_state:
                lines.append(f"Amenaza hasta ahora: {previous_journal.entity_state}")

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

    def _amenaza_block(self, beat_number: int, entities: list[Entity]) -> list[str]:
        """Solo los campos que la exposición del acto permite ver de cada entidad.

        Nunca la ficha completa si la exposición no la pide: con «señales» la Voz
        no recibe ni el nombre ni la naturaleza, así no puede revelarlos.
        """
        lines = [
            "AMENAZA EN ESTE ACTO (revelá solo lo que se indica):",
            "«Cómo se percibe» es un repertorio para todo el relato, no una lista a cumplir: "
            "usá solo lo que pida «Cómo mostrarla» y lo que encaje con el EVENTO.",
        ]
        for e in entities:
            exposure = self._beat_repo.exposure_for(beat_number, e.reveal_level)
            show = exposure.get("show", ["manifestations"])
            head = []
            if "name" in show and e.name:
                head.append(e.name)
            if "nature" in show:
                head.append(e.nature_label or e.nature_id)
            lines.append(f"- {' — '.join(head) if head else f'Presencia {e.order_index + 1}'}")
            for key, label in (
                ("description", "Qué es"),
                ("manifestations", "Cómo se percibe"),
                ("limits", "Límites"),
            ):
                value = getattr(e, key)
                if key in show and value:
                    lines.append(f"  {label}: {value}")
            if exposure.get("guide"):
                lines.append(f"  Cómo mostrarla: {exposure['guide']}")
        return lines
