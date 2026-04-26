"""Tests Spec-081 — dominio: NarrativeAnchors (5 pilares de resonancia), MacroBeat, Scenario."""

import uuid

from src.domain.models import (
    Beat,
    MacroBeat,
    NarrativeAnchors,
    Scenario,
)

_STORY_ID = uuid.uuid4()

_SAMPLE_ANCHORS = NarrativeAnchors(
    story_id=_STORY_ID,
    resonance_hamartia="Irene carga con la culpa de haber dejado a su madre sola.",
    resonance_hybris="La familia entra al monte de noche ignorando la advertencia.",
    resonance_anagnorisis="La figura de María inmóvil en el claro del monte, mirándolos.",
    resonance_peripeteia="Monte de los Espinillos: espinillos cerrados, barro, relámpagos sin salida.",
    resonance_residual="Irene ya no puede cerrar los ojos sin ver el claro del monte.",
)


class TestNarrativeAnchors:
    """A3 — NarrativeAnchors tiene los 5 campos de resonancia narrativa (Spec-081)."""

    def test_all_fields_populated(self):
        assert _SAMPLE_ANCHORS.resonance_hamartia != ""
        assert _SAMPLE_ANCHORS.resonance_hybris != ""
        assert _SAMPLE_ANCHORS.resonance_anagnorisis != ""
        assert _SAMPLE_ANCHORS.resonance_peripeteia != ""
        assert _SAMPLE_ANCHORS.resonance_residual != ""

    def test_constructed_from_dict(self):
        data = {
            "story_id": str(_STORY_ID),
            "resonance_hamartia": "La grieta del narrador",
            "resonance_hybris": "La transgresión",
            "resonance_anagnorisis": "El detalle que no puede ser",
            "resonance_peripeteia": "El entorno como trampa",
            "resonance_residual": "La mancha que permanece",
        }
        anchors = NarrativeAnchors(**data)
        assert anchors.resonance_hamartia == "La grieta del narrador"
        assert anchors.resonance_residual == "La mancha que permanece"

    def test_story_id_is_preserved(self):
        assert _SAMPLE_ANCHORS.story_id == _STORY_ID

    def test_each_pillar_maps_to_freytag_beat(self):
        """Cada pilar corresponde a un estadio de Freytag."""
        # beat 1 = hamartia (Exposición), beat 5 = residual (Desenlace)
        assert "culpa" in _SAMPLE_ANCHORS.resonance_hamartia
        assert "monte" in _SAMPLE_ANCHORS.resonance_residual


class TestMacroBeatNewFields:
    """A4 — MacroBeat acepta narrative_context y memory_snapshot como opcionales."""

    def test_macro_beat_defaults_are_none(self):
        beat = MacroBeat(number=1, summary="Apertura del relato")
        assert beat.active_scenario_id is None
        assert beat.narrative_context is None
        assert beat.memory_snapshot is None

    def test_macro_beat_accepts_new_fields(self):
        beat = MacroBeat(
            number=2,
            summary="El conflicto",
            active_scenario_id="some-uuid",
            narrative_context="ACTO: accion_ascendente\n...",
            memory_snapshot='{"last_events": "..."}',
        )
        assert beat.narrative_context.startswith("ACTO:")
        assert "last_events" in beat.memory_snapshot

    def test_beat_alias_is_macro_beat(self):
        """Beat es alias de MacroBeat — compatibilidad hacia atrás."""
        beat = Beat(number=1, summary="Test")
        assert isinstance(beat, MacroBeat)


class TestScenario:
    def test_scenario_fields(self):
        s = Scenario(story_id=_STORY_ID, order_index=1, name="La casa de la abuela")
        assert s.order_index == 1
        assert s.name == "La casa de la abuela"
        assert s.id is not None

    def test_scenario_order_preserved(self):
        scenarios = [
            Scenario(story_id=_STORY_ID, order_index=i, name=f"Escenario {i}")
            for i in range(1, 4)
        ]
        assert [s.order_index for s in scenarios] == [1, 2, 3]
