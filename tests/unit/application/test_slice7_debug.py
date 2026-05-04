"""Tests para DebugCollector y DebugMarkdownRenderer — Slice 7 (Spec-038).

Verifica:
- LLMCallRecord tiene narrative_context (no context_strategy)
- DebugCollector.record() acepta narrative_context
- DebugMarkdownRenderer muestra narrative_context en llamadas voz
- El campo no aparece en llamadas que no lo tienen
"""

import pytest

from src.application.services.debug_collector import (
    DebugCollector,
    LLMCallRecord,
)


def _make_record(**overrides) -> dict:
    base = dict(
        role="voz",
        beat_number=1,
        source_component="VozUseCase (voz_use_case.py)",
        model="qwen2.5:14b",
        temperature=0.6,
        num_ctx=6144,
        num_predict=600,
        system_prompt="Sos Irene, narrando en primera persona.",
        user_prompt="ACTO 1: Exposición\n\nEscribí el fragmento.",
        raw_response="La familia llegó al campo en silencio.",
        normalized_response="La familia llegó al campo en silencio.",
        parser_result="n/a",
        elapsed_s=2.4,
    )
    base.update(overrides)
    return base


class TestLLMCallRecordNarrativeContext:
    """LLMCallRecord tiene narrative_context (no context_strategy)."""

    def test_has_narrative_context_field(self):
        r = LLMCallRecord(
            role="voz",
            beat_number=1,
            source_component="VozUseCase",
            model="qwen2.5:14b",
            temperature=0.6,
            num_ctx=6144,
            num_predict=600,
            system_prompt=None,
            user_prompt="prompt",
            raw_response="respuesta",
            normalized_response="respuesta",
            parser_result="n/a",
            elapsed_s=1.0,
            narrative_context="ACTO 1: contexto pre-baked.",
        )
        assert r.narrative_context == "ACTO 1: contexto pre-baked."

    def test_narrative_context_defaults_to_none(self):
        r = LLMCallRecord(
            role="mapper",
            beat_number=None,
            source_component="SynopsisBeatMapper",
            model="qwen2.5:14b",
            temperature=0.4,
            num_ctx=4096,
            num_predict=512,
            system_prompt=None,
            user_prompt="prompt",
            raw_response="resp",
            normalized_response="resp",
            parser_result="ok: 5 beats",
            elapsed_s=3.0,
        )
        assert r.narrative_context is None

    def test_no_context_strategy_field(self):
        r = LLMCallRecord(
            role="voz",
            beat_number=1,
            source_component="VozUseCase",
            model="model",
            temperature=0.6,
            num_ctx=None,
            num_predict=None,
            system_prompt=None,
            user_prompt="p",
            raw_response="r",
            normalized_response="r",
            parser_result="n/a",
            elapsed_s=1.0,
        )
        assert not hasattr(r, "context_strategy")


class TestDebugCollectorRecordNarrativeContext:
    """DebugCollector.record() acepta y almacena narrative_context."""

    def test_record_stores_narrative_context(self):
        c = DebugCollector()
        c.record(**_make_record(narrative_context="ACTO 1: texto del contexto."))
        assert c.records[0].narrative_context == "ACTO 1: texto del contexto."

    def test_record_narrative_context_default_none(self):
        c = DebugCollector()
        c.record(**_make_record())
        assert c.records[0].narrative_context is None

    def test_record_does_not_accept_context_strategy(self):
        """context_strategy ya no es un parámetro válido del record."""
        c = DebugCollector()
        with pytest.raises(TypeError):
            c.record(**_make_record(context_strategy="none"))


class TestDebugRendererNarrativeContext:
    """DebugMarkdownRenderer incluye narrative_context en el output."""

    def test_narrative_context_appears_in_voz_section(self, tmp_path):
        c = DebugCollector()
        c.record(
            **_make_record(
                narrative_context="ACTO 1: Exposición\nARCO EMOCIONAL: calma → inquietud"
            )
        )
        path = c.write(
            tmp_path,
            {
                "title": "Test",
                "profile": "ollama-qwen25-14b",
                "provider": "ollama",
                "story_id": "xyz",
            },
        )
        content = path.read_text(encoding="utf-8")
        assert "Narrative Context" in content
        assert "ACTO 1: Exposición" in content

    def test_narrative_context_absent_when_none(self, tmp_path):
        c = DebugCollector()
        c.record(**_make_record(narrative_context=None))
        path = c.write(tmp_path, {})
        content = path.read_text(encoding="utf-8")
        assert "Narrative Context" not in content

    def test_no_context_strategy_in_output(self, tmp_path):
        c = DebugCollector()
        c.record(**_make_record())
        path = c.write(tmp_path, {})
        content = path.read_text(encoding="utf-8")
        assert "Context Strategy" not in content

    def test_multiple_beats_narrative_context(self, tmp_path):
        c = DebugCollector()
        for i in range(1, 4):
            c.record(
                **_make_record(
                    beat_number=i,
                    narrative_context=f"ACTO {i}: contexto del beat {i}.",
                )
            )
        path = c.write(tmp_path, {})
        content = path.read_text(encoding="utf-8")
        for i in range(1, 4):
            assert f"contexto del beat {i}" in content
