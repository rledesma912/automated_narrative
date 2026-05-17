"""Tests para NarrativeContextAssembler — Spec 063 Slice D."""

import uuid
from unittest.mock import MagicMock

import pytest

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.narrative_context_assembler import NarrativeContextAssembler
from src.application.services.story_analyst_service import StoryAnalystService
from src.domain.models import MacroBeat, NarrativeAnchors, NarrativeJournal

_STORY_ID = uuid.uuid4()
_ANCHORS = NarrativeAnchors(
    story_id=_STORY_ID,
    resonance_hamartia="Irene llega tranquila.",
    resonance_hybris="Presencia que imita conocidos.",
    resonance_anagnorisis="La figura inmóvil en el claro.",
    resonance_peripeteia="Monte: espinillos, barro, relámpagos.",
    resonance_residual="Irene ya no puede cerrar los ojos.",
)


@pytest.fixture
def repo() -> BeatSpecRepository:
    return BeatSpecRepository()


@pytest.fixture
def assembler(repo) -> NarrativeContextAssembler:
    return NarrativeContextAssembler(repo)


def _beat_anchors(beat_id: int, _repo: BeatSpecRepository | None = None) -> dict:
    analyst = StoryAnalystService(MagicMock(), MagicMock())
    return analyst.resolve_beat_anchors(_ANCHORS, beat_id)


def _beat(number: int, summary: str = "La familia llega.", scenario: str = "La casa") -> MacroBeat:
    return MacroBeat(number=number, summary=summary, active_scenario_id=scenario, status="pending")


class TestNarrativeContextAssemblerBasic:
    def test_retorna_string_no_vacio(self, assembler, repo):
        beat = _beat(1)
        result = assembler.assemble(beat, _beat_anchors(1, repo))
        assert isinstance(result, str) and len(result) > 0

    def test_contiene_summary(self, assembler, repo):
        beat = _beat(1, summary="La abuela advierte sobre el monte.")
        result = assembler.assemble(beat, _beat_anchors(1, repo))
        assert "La abuela advierte sobre el monte." in result

    def test_contiene_resonancia(self, assembler, repo):
        beat = _beat(1)
        anchors = _beat_anchors(1, repo)
        result = assembler.assemble(beat, anchors)
        assert anchors["resonance"] in result

    def test_contiene_label_voz(self, assembler, repo):
        beat = _beat(1)
        anchors = _beat_anchors(1, repo)
        result = assembler.assemble(beat, anchors)
        assert anchors["label_voz"] in result

    def test_contiene_escenario_activo(self, assembler, repo):
        beat = _beat(1, scenario="Monte de los Espinillos")
        result = assembler.assemble(beat, _beat_anchors(1, repo))
        assert "Monte de los Espinillos" in result

    def test_contiene_label_escenario_activo(self, assembler, repo):
        beat = _beat(2)
        result = assembler.assemble(beat, _beat_anchors(2, repo))
        assert "ESCENARIO:" in result

    def test_contiene_beat_spec_nombre(self, assembler, repo):
        beat = _beat(1)
        result = assembler.assemble(beat, _beat_anchors(1, repo))
        assert "exposicion" in result.lower() or "ACTO" in result

    def test_contiene_restricciones(self, assembler, repo):
        beat = _beat(1)
        result = assembler.assemble(beat, _beat_anchors(1, repo))
        assert "FIDELIDAD" in result or "PROHIBIDO" in result


class TestNarrativeContextAssemblerSnapshot:
    def test_sin_journal_no_incluye_seccion_memoria(self, assembler, repo):
        beat = _beat(1)
        result = assembler.assemble(beat, _beat_anchors(1, repo), previous_journal=None)
        assert "MEMORIA DEL ACTO ANTERIOR" not in result

    def test_con_journal_incluye_last_events(self, assembler, repo):
        beat = _beat(2)
        journal = NarrativeJournal(
            last_events="La familia llegó a la fiesta.",
            unresolved_mysteries="",
            physical_emotional_state="Tranquilos",
        )
        result = assembler.assemble(beat, _beat_anchors(2, repo), previous_journal=journal)
        assert "La familia llegó a la fiesta." in result

    def test_con_journal_incluye_seccion_memoria(self, assembler, repo):
        beat = _beat(2)
        journal = NarrativeJournal(last_events="Algo pasó.", physical_emotional_state="")
        result = assembler.assemble(beat, _beat_anchors(2, repo), previous_journal=journal)
        assert "MEMORIA DEL ACTO ANTERIOR" in result

    def test_journal_vacio_no_incluye_seccion_memoria(self, assembler, repo):
        beat = _beat(2)
        journal = NarrativeJournal()
        result = assembler.assemble(beat, _beat_anchors(2, repo), previous_journal=journal)
        assert "MEMORIA DEL ACTO ANTERIOR" not in result


class TestNarrativeContextAssemblerReglas:
    def test_reglas_activas_se_incluyen(self, assembler, repo):
        beat = _beat(1)
        result = assembler.assemble(
            beat, _beat_anchors(1, repo), active_rules=["No cruzar el monte de noche"]
        )
        assert "No cruzar el monte de noche" in result

    def test_sin_reglas_activas_no_incluye_seccion(self, assembler, repo):
        beat = _beat(1)
        result = assembler.assemble(beat, _beat_anchors(1, repo), active_rules=[])
        assert "REGLAS ESPECÍFICAS" not in result
