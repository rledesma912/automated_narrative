"""Tests del EventBus (Spec-460 T2.3)."""

import pytest

from src.application.services.event_bus import EventBus, job_channel
from src.domain.streaming import StreamEvent, StreamEventType


def _evt(kind: StreamEventType = StreamEventType.STATUS, **data) -> StreamEvent:
    return StreamEvent(event=kind, data=data)


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


def test_ids_monotonicos_por_canal(bus: EventBus):
    ids_a = [bus.publish("a", _evt(i=i)).id for i in range(3)]
    ids_b = [bus.publish("b", _evt(i=i)).id for i in range(2)]

    assert ids_a == [1, 2, 3]
    assert ids_b == [1, 2]


def test_publish_no_modifica_el_evento_original(bus: EventBus):
    original = _evt(x=1)

    published = bus.publish("a", original)

    assert original.id is None
    assert published.id == 1


def test_fan_out_a_todos_los_suscriptores(bus: EventBus):
    q1, _ = bus.subscribe("a")
    q2, _ = bus.subscribe("a")
    q_otro, _ = bus.subscribe("b")

    bus.publish("a", _evt(x=1))

    assert q1.get_nowait().data == {"x": 1}
    assert q2.get_nowait().data == {"x": 1}
    assert q_otro.empty()


def test_replay_completo_para_suscriptor_tardio(bus: EventBus):
    for i in range(3):
        bus.publish("a", _evt(i=i))

    _, replay = bus.subscribe("a")

    assert [e.data["i"] for e in replay] == [0, 1, 2]


def test_replay_desde_last_event_id(bus: EventBus):
    for i in range(5):
        bus.publish("a", _evt(i=i))

    _, replay = bus.subscribe("a", last_event_id=3)

    assert [e.id for e in replay] == [4, 5]


def test_last_event_id_al_dia_no_repite_nada(bus: EventBus):
    for i in range(2):
        bus.publish("a", _evt(i=i))

    _, replay = bus.subscribe("a", last_event_id=2)

    assert replay == []


def test_heartbeat_en_vivo_sin_id_ni_replay(bus: EventBus):
    queue, _ = bus.subscribe("a")

    hb = bus.publish("a", _evt(StreamEventType.HEARTBEAT, alive=True))
    bus.publish("a", _evt(x=1))

    assert hb.id is None
    assert queue.get_nowait().event == StreamEventType.HEARTBEAT
    _, replay = bus.subscribe("a")
    assert [e.event for e in replay] == [StreamEventType.STATUS]
    assert replay[0].id == 1  # el heartbeat no consume ids


def test_replay_respeta_maxlen():
    bus = EventBus(replay_maxlen=3)
    for i in range(5):
        bus.publish("a", _evt(i=i))

    _, replay = bus.subscribe("a")

    assert [e.id for e in replay] == [3, 4, 5]


def test_unsubscribe_deja_de_recibir(bus: EventBus):
    queue, _ = bus.subscribe("a")
    bus.unsubscribe("a", queue)

    bus.publish("a", _evt(x=1))

    assert queue.empty()


def test_drop_descarta_canal_y_replay(bus: EventBus):
    bus.publish("a", _evt(x=1))
    assert bus.has_channel("a")

    bus.drop("a")

    assert not bus.has_channel("a")
    _, replay = bus.subscribe("a")
    assert replay == []
    assert bus.publish("a", _evt(x=2)).id == 1  # canal nuevo, ids desde 1


def test_job_channel():
    assert job_channel("abc") == "job:abc"
