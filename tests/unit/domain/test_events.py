"""Tests para src/domain/events.py (Spec-500 S-A)."""

from src.domain.events import PhaseEvent, PipelinePhaseData


class TestPhaseEvent:
    def test_all_phases_are_string_enum_values(self):
        for member in PhaseEvent:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()

    def test_plan_ready_is_present(self):
        assert PhaseEvent.PLAN_READY.value == "plan_ready"

    def test_beat_lifecycle_phases(self):
        assert PhaseEvent.BEAT_START.value == "beat_start"
        assert PhaseEvent.MAPPER_DONE.value == "mapper_done"
        assert PhaseEvent.VOZ_DONE.value == "voz_done"
        assert PhaseEvent.JOURNAL_DONE.value == "journal_done"
        assert PhaseEvent.BEAT_COMPLETE.value == "beat_complete"

    def test_analyst_and_resolver_phases(self):
        assert PhaseEvent.ANALYST_START.value == "analyst_start"
        assert PhaseEvent.ANALYST_DONE.value == "analyst_done"
        assert PhaseEvent.RESOLVER_START.value == "resolver_start"
        assert PhaseEvent.RESOLVER_DONE.value == "resolver_done"


class TestPipelinePhaseData:
    def test_minimal_event(self):
        event = PipelinePhaseData(phase=PhaseEvent.ANALYST_DONE)
        assert event.phase == PhaseEvent.ANALYST_DONE
        assert event.beat_number is None
        assert event.step_label is None
        assert event.elapsed_s is None
        assert event.extra == {}

    def test_event_with_beat_number(self):
        event = PipelinePhaseData(phase=PhaseEvent.BEAT_COMPLETE, beat_number=3)
        assert event.beat_number == 3

    def test_event_with_step_label(self):
        event = PipelinePhaseData(phase=PhaseEvent.STEP_START, step_label="Analizando sinopsis")
        assert event.step_label == "Analizando sinopsis"

    def test_event_with_elapsed(self):
        event = PipelinePhaseData(phase=PhaseEvent.VOZ_DONE, elapsed_s=1.234567)
        assert event.elapsed_s == 1.234567

    def test_event_with_num_beats(self):
        event = PipelinePhaseData(phase=PhaseEvent.PLAN_READY, num_beats=5)
        assert event.num_beats == 5

    def test_event_with_extra(self):
        event = PipelinePhaseData(
            phase=PhaseEvent.ANALYST_DONE,
            extra={"anchors_count": 5, "model": "mistral:latest"},
        )
        assert event.extra["anchors_count"] == 5
        assert event.extra["model"] == "mistral:latest"

    def test_to_dict_minimal(self):
        event = PipelinePhaseData(phase=PhaseEvent.ANALYST_DONE)
        d = event.to_dict()
        assert d == {"phase": "analyst_done"}

    def test_to_dict_with_all_fields(self):
        event = PipelinePhaseData(
            phase=PhaseEvent.BEAT_COMPLETE,
            beat_number=2,
            step_label="Narrando beat 2/5",
            elapsed_s=2.5,
            num_beats=5,
            extra={"llm_elapsed": 2.1},
        )
        d = event.to_dict()
        assert d["phase"] == "beat_complete"
        assert d["beat_number"] == 2
        assert d["step_label"] == "Narrando beat 2/5"
        assert d["elapsed_s"] == 2.5
        assert d["num_beats"] == 5
        assert d["llm_elapsed"] == 2.1

    def test_to_dict_elapsed_rounded(self):
        event = PipelinePhaseData(phase=PhaseEvent.VOZ_DONE, elapsed_s=1.23456789)
        d = event.to_dict()
        assert d["elapsed_s"] == 1.235

    def test_to_dict_without_optional_fields(self):
        event = PipelinePhaseData(phase=PhaseEvent.PLAN_READY, num_beats=5)
        d = event.to_dict()
        assert "beat_number" not in d
        assert "step_label" not in d
        assert "elapsed_s" not in d

    def test_extra_overrides_to_dict_fields(self):
        event = PipelinePhaseData(
            phase=PhaseEvent.BEAT_COMPLETE,
            beat_number=3,
            extra={"beat_number": 99, "custom": "value"},
        )
        d = event.to_dict()
        assert d["beat_number"] == 99
        assert d["custom"] == "value"
