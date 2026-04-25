"""Tests unitarios para DebugCollector y NullDebugCollector."""


import pytest

from src.application.services.debug_collector import (
    DebugCollector,
    LLMCallRecord,
    NullDebugCollector,
)


def _make_record(**overrides) -> dict:
    base = dict(
        role="mapper",
        beat_number=None,
        source_component="SynopsisBeatMapper (synopsis_beat_mapper.py)",
        model="mistral:latest",
        temperature=0.3,
        num_ctx=4096,
        num_predict=800,
        system_prompt="You are a narrator.",
        user_prompt="Write beat 1.",
        raw_response="<think>thinking</think>\n## Beat 1\nSomething happened.",
        normalized_response="## Beat 1\nSomething happened.",
        parser_result="ok: 5 beats",
        elapsed_s=8.23,
    )
    base.update(overrides)
    return base


class TestNullDebugCollector:
    def test_is_not_active(self):
        c = NullDebugCollector()
        assert c.is_active() is False

    def test_record_does_not_accumulate(self):
        c = NullDebugCollector()
        c.record(**_make_record())
        c.record(**_make_record())
        assert len(c.records) == 0

    def test_write_returns_output_dir(self, tmp_path):
        c = NullDebugCollector()
        result = c.write(tmp_path, {})
        assert result == tmp_path


class TestDebugCollector:
    def test_is_active(self):
        c = DebugCollector()
        assert c.is_active() is True

    def test_accumulates_records(self):
        c = DebugCollector()
        c.record(**_make_record())
        c.record(**_make_record(role="voz", beat_number=1))
        c.record(**_make_record(role="journal", beat_number=1))
        assert len(c.records) == 3

    def test_record_fields_stored_correctly(self):
        c = DebugCollector()
        data = _make_record()
        c.record(**data)
        r: LLMCallRecord = c.records[0]
        assert r.role == "mapper"
        assert r.model == "mistral:latest"
        assert r.raw_response == data["raw_response"]
        assert r.normalized_response == data["normalized_response"]
        assert r.parser_result == "ok: 5 beats"
        assert r.elapsed_s == pytest.approx(8.23)

    def test_write_generates_file(self, tmp_path):
        c = DebugCollector()
        c.record(**_make_record())
        path = c.write(tmp_path, {"title": "Test", "profile": "ollama-mistral", "provider": "ollama", "story_id": "abc"})
        assert path.exists()
        assert path.suffix == ".md"
        assert "debug_prompts_responses_" in path.name

    def test_write_file_contains_raw_response(self, tmp_path):
        c = DebugCollector()
        raw = "<think>thinking</think>\nThe story begins here."
        c.record(**_make_record(raw_response=raw))
        path = c.write(tmp_path, {})
        content = path.read_text(encoding="utf-8")
        assert raw in content

    def test_write_file_contains_parser_result(self, tmp_path):
        c = DebugCollector()
        c.record(**_make_record(parser_result="ok: 5 beats"))
        path = c.write(tmp_path, {})
        content = path.read_text(encoding="utf-8")
        assert "ok: 5 beats" in content

    def test_summary_table_row_count(self, tmp_path):
        c = DebugCollector()
        for i in range(3):
            c.record(**_make_record(role="voz", beat_number=i + 1))
        path = c.write(tmp_path, {})
        content = path.read_text(encoding="utf-8")
        # 3 data rows + header row + TOTAL row = 5 pipe-separated lines in table
        table_rows = [line for line in content.splitlines() if line.startswith("| ") and "voz" in line]
        assert len(table_rows) == 3


class TestSourceLabel:
    def test_returns_class_and_filename(self):
        c = DebugCollector()
        label = DebugCollector.source_label(c)
        assert "DebugCollector" in label
        assert "debug_collector.py" in label

    def test_works_for_arbitrary_object(self):
        class FakeMapper:
            pass

        label = DebugCollector.source_label(FakeMapper())
        assert "FakeMapper" in label
