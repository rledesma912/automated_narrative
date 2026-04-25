"""Tests Spec-038 — dominio: NarrativeAnchors, Scenario, MacroBeat, resolve_beat_anchors."""

import uuid


from src.domain.models import (
    Beat,
    MacroBeat,
    NarrativeAnchors,
    Scenario,
    resolve_beat_anchors,
)

_STORY_ID = uuid.uuid4()

_SAMPLE_BEATS_SPEC = [
    {
        "id": 1,
        "name": "exposicion",
        "anchor_priorities": {"principal": "initial_state", "contexto": "spatial_anchor"},
    },
    {
        "id": 2,
        "name": "accion_ascendente",
        "anchor_priorities": {"principal": "threat_nature", "contexto": "initial_state"},
    },
    {
        "id": 3,
        "name": "climax",
        "anchor_priorities": {"principal": "horror_peak", "contexto": "threat_nature"},
    },
    {
        "id": 4,
        "name": "accion_descendente",
        "anchor_priorities": {"principal": "spatial_anchor", "contexto": "threat_nature"},
    },
    {
        "id": 5,
        "name": "desenlace",
        "anchor_priorities": {"principal": "initial_state", "contexto": "threat_nature"},
    },
]

_SAMPLE_ANCHORS = NarrativeAnchors(
    story_id=_STORY_ID,
    initial_state="Irene llega tranquila, esperando un día de campo sin complicaciones.",
    threat_nature="Una presencia que imita a los conocidos para atraer hacia el monte.",
    horror_peak="La figura de María inmóvil en el claro del monte, mirándolos.",
    spatial_anchor="Monte de los Espinillos: espinillos bajos y cerrados, barro, relámpagos.",
)


class TestResolveAnchorsBeat1:
    """A1 — beat 1 usa initial_state como principal y spatial_anchor como contexto."""

    def test_beat1_principal_is_initial_state(self):
        result = resolve_beat_anchors(_SAMPLE_ANCHORS, 1, _SAMPLE_BEATS_SPEC)
        assert result["principal"] == _SAMPLE_ANCHORS.initial_state

    def test_beat1_contexto_is_spatial_anchor(self):
        result = resolve_beat_anchors(_SAMPLE_ANCHORS, 1, _SAMPLE_BEATS_SPEC)
        assert result["contexto"] == _SAMPLE_ANCHORS.spatial_anchor


class TestResolveAnchorsBeat3:
    """A2 — beat 3 (clímax) usa horror_peak como principal."""

    def test_beat3_principal_is_horror_peak(self):
        result = resolve_beat_anchors(_SAMPLE_ANCHORS, 3, _SAMPLE_BEATS_SPEC)
        assert result["principal"] == _SAMPLE_ANCHORS.horror_peak

    def test_beat3_contexto_is_threat_nature(self):
        result = resolve_beat_anchors(_SAMPLE_ANCHORS, 3, _SAMPLE_BEATS_SPEC)
        assert result["contexto"] == _SAMPLE_ANCHORS.threat_nature


class TestResolveAnchorsEdgeCases:
    def test_unknown_beat_id_returns_empty(self):
        result = resolve_beat_anchors(_SAMPLE_ANCHORS, 99, _SAMPLE_BEATS_SPEC)
        assert result == {}

    def test_all_five_beats_resolve_without_error(self):
        for beat_id in range(1, 6):
            result = resolve_beat_anchors(_SAMPLE_ANCHORS, beat_id, _SAMPLE_BEATS_SPEC)
            assert "principal" in result
            assert "contexto" in result
            assert result["principal"] != ""
            assert result["contexto"] != ""


class TestNarrativeAnchors:
    """A3 — NarrativeAnchors tiene los 4 campos no vacíos."""

    def test_all_fields_populated(self):
        assert _SAMPLE_ANCHORS.initial_state != ""
        assert _SAMPLE_ANCHORS.threat_nature != ""
        assert _SAMPLE_ANCHORS.horror_peak != ""
        assert _SAMPLE_ANCHORS.spatial_anchor != ""

    def test_constructed_from_dict(self):
        data = {
            "story_id": str(_STORY_ID),
            "initial_state": "Estado inicial",
            "threat_nature": "Naturaleza amenaza",
            "horror_peak": "Pico de horror",
            "spatial_anchor": "Anclaje espacial",
        }
        anchors = NarrativeAnchors(**data)
        assert anchors.initial_state == "Estado inicial"
        assert anchors.horror_peak == "Pico de horror"


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
