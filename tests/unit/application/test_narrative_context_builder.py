"""Tests para build_narrative_context() y build_voz_*() (Spec-038, B3/B4/B6/B7/B10)."""

import json
import uuid

import pytest

from src.application.services import PromptBuilder
from src.domain.models import MacroBeat, NarrativeAnchors, Story, resolve_beat_anchors


def _make_story(**kwargs):
    defaults = dict(
        title="El Monte Prohibido",
        protagonista="Irene, Ricardo, Mariano",
        relator="Irene",
        escenarios="Monte de los Espinillos",
        sinopsis="La familia llega al campo y entra al monte de noche.",
        atmosfera="terror paranormal",
        reglas=["Ricardo ignora lo sobrenatural.", "Las apariciones no atacan físicamente."],
    )
    defaults.update(kwargs)
    return Story(**defaults)


_STORY_ID = uuid.uuid4()
_ANCHORS = NarrativeAnchors(
    story_id=_STORY_ID,
    initial_state="Irene llega tranquila, sin sospechar nada.",
    threat_nature="Una presencia que imita a los conocidos.",
    horror_peak="La figura de María inmóvil en el claro del monte.",
    spatial_anchor="Monte de los Espinillos: espinillos cerrados, barro, relámpagos.",
)


def _beat_anchors(beat_id: int) -> dict:
    builder = PromptBuilder()
    return resolve_beat_anchors(_ANCHORS, beat_id, builder._beats_spec)


def _make_beat(number: int, summary: str = "La familia llega temprano.", scenario: str = "La casa de la abuela") -> MacroBeat:
    return MacroBeat(
        number=number,
        summary=summary,
        active_scenario_id=scenario,
        status="pending",
    )


def _make_beat_with_nc(number: int) -> MacroBeat:
    builder = PromptBuilder()
    anchors = _beat_anchors(number)
    beat = _make_beat(number)
    beat.narrative_context = builder.build_narrative_context(beat, anchors)
    return beat


class TestBuildNarrativeContext:
    """B3 — build_narrative_context() produce un string con todos los insumos."""

    def test_returns_non_empty_string(self):
        builder = PromptBuilder()
        beat = _make_beat(1)
        result = builder.build_narrative_context(beat, _beat_anchors(1))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_beat_summary(self):
        """B3 — contiene el summary (synopsis_event)."""
        builder = PromptBuilder()
        beat = _make_beat(1, summary="La abuela advierte sobre el monte.")
        result = builder.build_narrative_context(beat, _beat_anchors(1))
        assert "La abuela advierte sobre el monte." in result

    def test_contains_anchor_principal(self):
        """B3 — contiene el valor del anclaje principal."""
        builder = PromptBuilder()
        beat = _make_beat(1)
        anchors = _beat_anchors(1)
        result = builder.build_narrative_context(beat, anchors)
        assert anchors["principal"] in result

    def test_contains_anchor_contexto(self):
        """B3 — contiene el valor del anclaje de contexto."""
        builder = PromptBuilder()
        beat = _make_beat(1)
        anchors = _beat_anchors(1)
        result = builder.build_narrative_context(beat, anchors)
        assert anchors["contexto"] in result

    def test_contains_last_events_from_snapshot(self):
        """B3 — contiene last_events del memory_snapshot anterior."""
        builder = PromptBuilder()
        beat = _make_beat(2)
        snapshot = json.dumps({
            "last_events": "La familia llegó a la fiesta.",
            "unresolved_mysteries": "",
            "physical_emotional_state": "Tranquilos",
        })
        result = builder.build_narrative_context(beat, _beat_anchors(2), prev_snapshot=snapshot)
        assert "La familia llegó a la fiesta." in result

    def test_beat1_has_no_prev_memory_section(self):
        """Beat 1 sin snapshot no incluye sección MEMORIA."""
        builder = PromptBuilder()
        beat = _make_beat(1)
        result = builder.build_narrative_context(beat, _beat_anchors(1), prev_snapshot=None)
        assert "MEMORIA DEL ACTO ANTERIOR" not in result

    def test_beat2_with_snapshot_includes_memory_section(self):
        builder = PromptBuilder()
        beat = _make_beat(2)
        snapshot = json.dumps({"last_events": "Algo pasó.", "physical_emotional_state": ""})
        result = builder.build_narrative_context(beat, _beat_anchors(2), prev_snapshot=snapshot)
        assert "MEMORIA DEL ACTO ANTERIOR" in result
        assert "Algo pasó." in result

    def test_contains_beat_spec_info(self):
        """Contiene nombre e intent del acto desde el YAML."""
        builder = PromptBuilder()
        beat = _make_beat(1)
        result = builder.build_narrative_context(beat, _beat_anchors(1))
        assert "exposicion" in result.lower() or "ACTO" in result

    def test_contains_restrictions(self):
        """Contiene las restricciones must / must_not del YAML."""
        builder = PromptBuilder()
        beat = _make_beat(1)
        result = builder.build_narrative_context(beat, _beat_anchors(1))
        assert "RESTRICCIONES" in result or "Debe incluir" in result


class TestActiveScenarioInNarrativeContext:
    """B10 — narrative_context incluye el active_scenario del macro-beat."""

    def test_contains_active_scenario(self):
        builder = PromptBuilder()
        beat = _make_beat(1, scenario="Monte de los Espinillos")
        result = builder.build_narrative_context(beat, _beat_anchors(1))
        assert "Monte de los Espinillos" in result

    def test_escenario_activo_label_present(self):
        builder = PromptBuilder()
        beat = _make_beat(2, scenario="La estancia de la fiesta")
        result = builder.build_narrative_context(beat, _beat_anchors(2))
        assert "ESCENARIO ACTIVO" in result


class TestVozUserPrompt:
    """B4 — el user prompt del VOZ contiene narrative_context y NO la sinopsis completa."""

    def test_voz_user_prompt_contains_narrative_context(self):
        builder = PromptBuilder()
        beat = _make_beat_with_nc(1)
        prompt = builder.build_voz_user_prompt(beat)
        assert beat.narrative_context in prompt

    def test_voz_user_prompt_does_not_contain_full_sinopsis(self):
        """B4 — el user prompt no contiene la sinopsis completa de la historia."""
        builder = PromptBuilder()
        story = _make_story()
        beat = _make_beat_with_nc(2)
        prompt = builder.build_voz_user_prompt(beat)
        # La sinopsis completa no debería estar en el user prompt del VOZ
        assert story.sinopsis not in prompt

    def test_voz_user_prompt_not_empty(self):
        builder = PromptBuilder()
        beat = _make_beat_with_nc(3)
        prompt = builder.build_voz_user_prompt(beat)
        assert len(prompt) > 10


class TestVozSystemPrompt:
    """B6 — el system prompt del VOZ contiene protagonistas y reglas."""

    def test_system_prompt_contains_protagonistas(self):
        """B6 — system prompt tiene protagonistas."""
        builder = PromptBuilder()
        story = _make_story()
        system = builder.build_voice_system_compact(story)
        assert story.protagonista in system

    def test_system_prompt_contains_reglas(self):
        """B6 — system prompt tiene reglas del relato."""
        builder = PromptBuilder()
        story = _make_story()
        system = builder.build_voice_system_compact(story)
        for regla in story.reglas:
            assert regla in system

    def test_system_prompt_contains_relator(self):
        builder = PromptBuilder()
        story = _make_story()
        system = builder.build_voice_system_compact(story)
        assert story.relator in system

    def test_system_prompt_contains_atmosfera(self):
        builder = PromptBuilder()
        story = _make_story()
        system = builder.build_voice_system_compact(story)
        assert story.atmosfera in system


class TestNarrativeContextHasNoStoryConstants:
    """B7 — el narrative_context (user prompt del VOZ) NO contiene protagonistas ni reglas."""

    def test_narrative_context_has_no_protagonistas(self):
        """B7 — protagonistas son del system prompt, no del narrative_context."""
        builder = PromptBuilder()
        story = _make_story()
        beat = _make_beat(1, summary="La familia llega.")
        anchors = _beat_anchors(1)
        nc = builder.build_narrative_context(beat, anchors)
        # El narrative_context no debe listar los protagonistas
        assert story.protagonista not in nc

    def test_narrative_context_has_no_reglas(self):
        """B7 — las reglas son del system prompt, no del narrative_context."""
        builder = PromptBuilder()
        story = _make_story()
        beat = _make_beat(1)
        anchors = _beat_anchors(1)
        nc = builder.build_narrative_context(beat, anchors)
        for regla in story.reglas:
            assert regla not in nc
