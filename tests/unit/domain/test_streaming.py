"""Tests de StreamEvent (Spec-201 + Spec-460 T2.1)."""

import json

from src.domain.streaming import StreamEvent, StreamEventType


def test_to_sse_sin_id_mantiene_el_formato_actual():
    sse = StreamEvent(event=StreamEventType.BEAT_DONE, data={"number": 1}).to_sse()

    assert sse == {"event": "beat_done", "data": json.dumps({"number": 1})}


def test_to_sse_con_id_lo_incluye_como_string():
    sse = StreamEvent(event=StreamEventType.STATUS, data={"msg": "x"}, id=7).to_sse()

    assert sse["id"] == "7"


def test_to_sse_preserva_acentos():
    sse = StreamEvent(event=StreamEventType.STATUS, data={"msg": "Narrando acción"}).to_sse()

    assert "acción" in sse["data"]


def test_error_sigue_siendo_stream_error():
    """Spec-201: `error` está reservado por EventSource."""
    assert StreamEventType.ERROR.value == "stream_error"


def test_tipos_de_ciclo_de_vida_de_jobs():
    assert {
        StreamEventType.JOB_STARTED.value,
        StreamEventType.JOB_PROGRESS.value,
        StreamEventType.JOB_DONE.value,
        StreamEventType.JOB_FAILED.value,
        StreamEventType.SNAPSHOT.value,
    } == {"job_started", "job_progress", "job_done", "job_failed", "snapshot"}
