"""Tests del JobManager (Spec-460 T2.4–T2.8).

Usa el SQLJobRepository real sobre una DB temporal (el índice único parcial
participa de la idempotencia) y un repo de historias falso.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from src.application.services.event_bus import GLOBAL_CHANNEL, EventBus, job_channel
from src.application.services.job_manager import JobAlreadyActiveError, JobManager
from src.application.services.streaming_service import stage_event, stream_story
from src.config import settings
from src.domain.jobs import (
    CANCELLED_ERROR,
    INTERRUPTED_ERROR,
    NO_RESULT_ERROR,
    JobKind,
    JobStage,
    JobStatus,
)
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.database.connection import get_connection, init_db
from src.infrastructure.database.repositories.job_repository import SQLJobRepository

# ── Fakes ─────────────────────────────────────────────────────────────────────


class _FakeStoryRepo:
    def __init__(self) -> None:
        self.statuses: list[str] = []
        self.calls: list[str] = []
        self.titles: dict = {}

    async def update_status(self, story_id, status) -> None:
        self.statuses.append(getattr(status, "value", status))

    async def clear_story_artifacts(self, story_id) -> None:
        self.calls.append("clear")

    async def get_by_id(self, story_id):
        title = self.titles.get(story_id)
        return SimpleNamespace(title=title) if title is not None else None


class _FakeBeatRepo:
    def __init__(self) -> None:
        self.saved: list[str] = []

    async def save(self, beat, story_id) -> None:
        self.saved.append(beat.generated_act)


class _SlowDirector:
    """Pipeline lento: informa etapas y narra un beat cada `delay` segundos."""

    def __init__(self, beats: int = 5, delay: float = 0.05) -> None:
        self.prompt_builder = SimpleNamespace(num_beats=beats)
        self._beats = beats
        self._delay = delay

    async def execute_full(self, story, on_stage=None, **_kwargs):
        on_stage(JobStage.ANALYST, None)
        for n in range(1, self._beats + 1):
            on_stage(JobStage.VOZ, n)
            await asyncio.sleep(self._delay)  # "llamada LLM"
            yield SimpleNamespace(beat_type=None, generated_act=f"acto {n}"), None, 0.0


def _quick_run(narrative_id: str | None = None, total: int = 2):
    """Runner rápido: etapas + DONE."""

    async def _gen() -> AsyncIterator[StreamEvent]:
        yield stage_event(JobStage.ANALYST, None, total)
        for n in range(1, total + 1):
            yield stage_event(JobStage.VOZ, n, total)
            yield StreamEvent(event=StreamEventType.BEAT_DONE, data={"number": n})
        yield StreamEvent(event=StreamEventType.DONE, data={"narrative_id": narrative_id})

    return _gen


def _events_run(*events: StreamEvent, raise_exc: Exception | None = None):
    async def _gen() -> AsyncIterator[StreamEvent]:
        for e in events:
            yield e
        if raise_exc:
            raise raise_exc

    return _gen


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def job_repo(monkeypatch, tmp_path) -> SQLJobRepository:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    await init_db()
    return SQLJobRepository()


@pytest.fixture
def story_repo() -> _FakeStoryRepo:
    return _FakeStoryRepo()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def manager(bus, job_repo, story_repo) -> JobManager:
    return JobManager(bus, job_repo, story_repo)


async def _story(story_repo: _FakeStoryRepo, title: str = "La pena del colectivo"):
    story_id = uuid.uuid4()
    conn = await get_connection()
    await conn.execute("INSERT INTO story (id, title) VALUES (?, ?)", (str(story_id), title))
    await conn.commit()
    await conn.close()
    story_repo.titles[story_id] = title
    return SimpleNamespace(id=story_id, title=title)


def _drain(queue: asyncio.Queue) -> list[StreamEvent]:
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


# ── T2.4 submit ───────────────────────────────────────────────────────────────


async def test_submit_corre_el_pipeline_y_publica_en_ambos_canales(
    manager, bus, job_repo, story_repo
):
    story = await _story(story_repo)
    global_q, _ = bus.subscribe(GLOBAL_CHANNEL)

    narrative_id = str(uuid.uuid4())
    job = await manager.submit(story, JobKind.FULL_GENERATION, _quick_run(narrative_id, total=2))
    detail_q, replay = bus.subscribe(job_channel(job.id))
    await manager.wait(job.id)

    detail = replay + _drain(detail_q)
    assert [e.event for e in detail][-1] == StreamEventType.DONE
    assert [e.id for e in detail] == list(range(1, len(detail) + 1))

    glob = _drain(global_q)
    assert [e.event for e in glob] == [
        StreamEventType.JOB_STARTED,
        StreamEventType.JOB_PROGRESS,  # analyst
        StreamEventType.JOB_PROGRESS,  # voz 1
        StreamEventType.JOB_PROGRESS,  # voz 2
        StreamEventType.JOB_DONE,
    ]
    assert glob[0].data["title"] == "La pena del colectivo"
    assert (glob[2].data["stage"], glob[2].data["beat"], glob[2].data["total_beats"]) == (
        "voz",
        1,
        2,
    )
    assert glob[-1].data["narrative_id"] == narrative_id

    saved = await job_repo.get(job.id)
    assert saved.status == JobStatus.DONE
    assert (saved.stage, saved.beat, saved.total_beats) == (JobStage.VOZ, 2, 2)
    assert saved.started_at is not None and saved.finished_at is not None


async def test_done_guarda_narrative_id(manager, job_repo, story_repo):
    story = await _story(story_repo)
    narrative_id = str(uuid.uuid4())

    job = await manager.submit(story, JobKind.FULL_GENERATION, _quick_run(narrative_id))
    await manager.wait(job.id)

    assert str((await job_repo.get(job.id)).narrative_id) == narrative_id


async def test_narrative_id_invalido_no_rompe_el_cierre_del_job(manager, bus, job_repo, story_repo):
    story = await _story(story_repo)
    global_q, _ = bus.subscribe(GLOBAL_CHANNEL)

    job = await manager.submit(story, JobKind.FULL_GENERATION, _quick_run("no-es-uuid"))
    await manager.wait(job.id)

    saved = await job_repo.get(job.id)
    assert (saved.status, saved.narrative_id) == (JobStatus.DONE, None)
    assert _drain(global_q)[-1].event == StreamEventType.JOB_DONE
    assert not manager.is_running(job.id)


async def test_segundo_submit_con_job_activo_lanza_409_logico(manager, story_repo):
    story = await _story(story_repo)
    block = asyncio.Event()

    async def _hold() -> AsyncIterator[StreamEvent]:
        await block.wait()
        yield StreamEvent(event=StreamEventType.DONE, data={})

    first = await manager.submit(story, JobKind.FULL_GENERATION, lambda: _hold())

    with pytest.raises(JobAlreadyActiveError) as exc:
        await manager.submit(story, JobKind.FULL_GENERATION, _quick_run())
    assert exc.value.job_id == first.id

    block.set()
    await manager.wait(first.id)


async def test_submits_concurrentes_crean_un_solo_job(manager, story_repo):
    story = await _story(story_repo)
    block = asyncio.Event()

    async def _hold() -> AsyncIterator[StreamEvent]:
        await block.wait()  # el primer job sigue activo mientras llegan los demás
        yield StreamEvent(event=StreamEventType.DONE, data={})

    results = await asyncio.gather(
        *(manager.submit(story, JobKind.FULL_GENERATION, lambda: _hold()) for _ in range(5)),
        return_exceptions=True,
    )

    jobs = [r for r in results if not isinstance(r, Exception)]
    errors = [r for r in results if isinstance(r, JobAlreadyActiveError)]
    assert len(jobs) == 1 and len(errors) == 4
    assert {e.job_id for e in errors} == {jobs[0].id}
    block.set()
    await manager.wait(jobs[0].id)


# ── Fallos ────────────────────────────────────────────────────────────────────


async def test_evento_de_error_deja_el_job_failed(manager, bus, job_repo, story_repo):
    story = await _story(story_repo)
    global_q, _ = bus.subscribe(GLOBAL_CHANNEL)
    run = _events_run(StreamEvent(event=StreamEventType.ERROR, data={"msg": "Ollama caído"}))

    job = await manager.submit(story, JobKind.FULL_GENERATION, run)
    await manager.wait(job.id)

    saved = await job_repo.get(job.id)
    assert (saved.status, saved.error) == (JobStatus.FAILED, "Ollama caído")
    assert _drain(global_q)[-1].event == StreamEventType.JOB_FAILED


async def test_excepcion_del_runner_deja_el_job_failed(manager, bus, job_repo, story_repo):
    story = await _story(story_repo)
    run = _events_run(raise_exc=RuntimeError("boom"))

    job = await manager.submit(story, JobKind.FULL_GENERATION, run)
    detail_q, replay = bus.subscribe(job_channel(job.id))
    await manager.wait(job.id)

    saved = await job_repo.get(job.id)
    assert (saved.status, saved.error) == (JobStatus.FAILED, "boom")
    detail = replay + _drain(detail_q)
    assert detail[-1].event == StreamEventType.ERROR


async def test_runner_sin_done_ni_error_queda_failed(manager, job_repo, story_repo):
    story = await _story(story_repo)
    run = _events_run(stage_event(JobStage.ANALYST, None, 5))

    job = await manager.submit(story, JobKind.FULL_GENERATION, run)
    await manager.wait(job.id)

    saved = await job_repo.get(job.id)
    assert (saved.status, saved.error) == (JobStatus.FAILED, NO_RESULT_ERROR)


# ── T2.5 regeneración atómica ─────────────────────────────────────────────────


async def test_regenerate_limpia_artefactos_antes_del_pipeline(manager, story_repo):
    story = await _story(story_repo)

    def run() -> AsyncIterator[StreamEvent]:
        story_repo.calls.append("pipeline")
        return _quick_run()()

    job = await manager.submit(story, JobKind.FULL_GENERATION, run, regenerate=True)
    await manager.wait(job.id)

    assert story_repo.calls == ["clear", "pipeline"]


async def test_sin_regenerate_no_limpia(manager, story_repo):
    story = await _story(story_repo)

    job = await manager.submit(story, JobKind.FULL_GENERATION, _quick_run())
    await manager.wait(job.id)

    assert story_repo.calls == []


# ── T2.6 cancelación real (D7 portado) ────────────────────────────────────────


async def test_cancelar_detiene_el_pipeline_y_no_pisa_el_estado(manager, bus, job_repo, story_repo):
    """D7 portado: con JobManager, cancelar detiene el LLM y la historia queda failed."""
    story = await _story(story_repo)
    beat_repo = _FakeBeatRepo()
    global_q, _ = bus.subscribe(GLOBAL_CHANNEL)

    job = await manager.submit(
        story,
        JobKind.FULL_GENERATION,
        lambda: stream_story(_SlowDirector(), story, story_repo=story_repo, beat_repo=beat_repo),
    )
    await asyncio.sleep(0.12)  # ~2 beats narrados

    assert await manager.cancel(job.id) is True
    beats_al_cancelar = len(beat_repo.saved)
    await asyncio.sleep(0.4)  # si el pipeline siguiera vivo, narraría el resto

    assert 0 < beats_al_cancelar < 5
    assert len(beat_repo.saved) == beats_al_cancelar, "no deben narrarse beats tras cancelar"
    assert story_repo.statuses[-1] == "failed", f"estados: {story_repo.statuses}"
    assert "completed" not in story_repo.statuses
    saved = await job_repo.get(job.id)
    assert (saved.status, saved.error) == (JobStatus.FAILED, CANCELLED_ERROR)
    assert _drain(global_q)[-1].event == StreamEventType.JOB_FAILED


async def test_cancelar_publica_stream_error_en_el_canal_del_job(manager, bus, story_repo):
    story = await _story(story_repo)
    block = asyncio.Event()

    async def _hold() -> AsyncIterator[StreamEvent]:
        await block.wait()
        yield StreamEvent(event=StreamEventType.DONE, data={})

    job = await manager.submit(story, JobKind.FULL_GENERATION, lambda: _hold())
    detail_q, _ = bus.subscribe(job_channel(job.id))
    await asyncio.sleep(0)

    await manager.cancel(job.id)

    last = _drain(detail_q)[-1]
    assert last.event == StreamEventType.ERROR
    assert last.data == {"msg": CANCELLED_ERROR, "cancelled": True}


async def test_cancelar_job_inexistente_o_terminado_devuelve_false(manager, story_repo):
    story = await _story(story_repo)
    job = await manager.submit(story, JobKind.FULL_GENERATION, _quick_run())
    await manager.wait(job.id)

    assert await manager.cancel(job.id) is False
    assert await manager.cancel(uuid.uuid4()) is False


# ── T2.7 TTL, sesión huérfana (D5 portado) y snapshot ─────────────────────────


async def test_consumidor_que_se_va_no_bloquea_una_generacion_nueva(manager, bus, story_repo):
    """D5 portado: pestaña cerrada a mitad; el job termina solo; regenerar crea job nuevo."""
    story = await _story(story_repo)
    block = asyncio.Event()
    calls: list[str] = []

    async def _first() -> AsyncIterator[StreamEvent]:
        calls.append("primera")
        await block.wait()
        yield StreamEvent(event=StreamEventType.DONE, data={})

    first = await manager.submit(story, JobKind.FULL_GENERATION, lambda: _first())
    queue, _ = bus.subscribe(job_channel(first.id))
    bus.unsubscribe(job_channel(first.id), queue)  # pestaña cerrada
    block.set()
    await manager.wait(first.id)  # el job terminó sin consumidores

    def _second() -> AsyncIterator[StreamEvent]:
        calls.append("segunda")
        return _quick_run()()

    second = await manager.submit(story, JobKind.FULL_GENERATION, _second)
    await manager.wait(second.id)

    assert second.id != first.id
    assert calls == ["primera", "segunda"]


async def test_canal_del_job_se_descarta_tras_el_ttl(bus, job_repo, story_repo):
    manager = JobManager(bus, job_repo, story_repo, channel_ttl=0.05)
    story = await _story(story_repo)

    job = await manager.submit(story, JobKind.FULL_GENERATION, _quick_run())
    await manager.wait(job.id)
    assert bus.has_channel(job_channel(job.id))  # replay disponible al terminar

    await asyncio.sleep(0.1)

    assert not bus.has_channel(job_channel(job.id))


async def test_snapshot_incluye_activos_y_terminados_recientes(manager, story_repo):
    terminada = await _story(story_repo, "Terminada")
    en_curso = await _story(story_repo, "En curso")
    block = asyncio.Event()

    async def _hold() -> AsyncIterator[StreamEvent]:
        yield stage_event(JobStage.VOZ, 3, 5)
        await block.wait()
        yield StreamEvent(event=StreamEventType.DONE, data={})

    done_job = await manager.submit(terminada, JobKind.FULL_GENERATION, _quick_run())
    await manager.wait(done_job.id)
    active_job = await manager.submit(en_curso, JobKind.FULL_GENERATION, lambda: _hold())
    await asyncio.sleep(0.05)

    snap = await manager.snapshot()

    assert snap.event == StreamEventType.SNAPSHOT
    assert [(j["job_id"], j["title"], j["stage"], j["beat"]) for j in snap.data["active"]] == [
        (str(active_job.id), "En curso", "voz", 3)
    ]
    assert [(j["job_id"], j["status"]) for j in snap.data["recent"]] == [(str(done_job.id), "done")]

    block.set()
    await manager.wait(active_job.id)


async def test_snapshot_busca_el_titulo_de_jobs_de_otro_proceso(bus, job_repo, story_repo):
    """Jobs recuperados tras reinicio: el título sale del repo de historias."""
    story = await _story(story_repo, "Recuperada")
    await JobManager(bus, job_repo, story_repo).submit(story, JobKind.FULL_GENERATION, _quick_run())
    await asyncio.sleep(0.05)
    fresh = JobManager(bus, job_repo, story_repo)  # otro "proceso": no conoce el título

    snap = await fresh.snapshot()

    assert snap.data["recent"][0]["title"] == "Recuperada"


# ── T2.8 cierre del proceso ───────────────────────────────────────────────────


async def test_shutdown_deja_los_jobs_vivos_como_interrumpidos(manager, job_repo, story_repo):
    story = await _story(story_repo)
    block = asyncio.Event()

    async def _hold() -> AsyncIterator[StreamEvent]:
        await block.wait()
        yield StreamEvent(event=StreamEventType.DONE, data={})

    job = await manager.submit(story, JobKind.FULL_GENERATION, lambda: _hold())
    await asyncio.sleep(0)

    await manager.shutdown()

    saved = await job_repo.get(job.id)
    assert (saved.status, saved.error) == (JobStatus.FAILED, INTERRUPTED_ERROR)
    assert not manager.is_running(job.id)


async def test_cierre_de_la_app_interrumpe_los_jobs_del_singleton(job_repo, story_repo):
    """T2.8: el lifespan de FastAPI apaga el job_manager del proceso."""
    from src.main import app, lifespan
    from src.presentation.runtime import job_manager

    story = await _story(story_repo)
    block = asyncio.Event()

    async def _hold() -> AsyncIterator[StreamEvent]:
        await block.wait()
        yield StreamEvent(event=StreamEventType.DONE, data={})

    async with lifespan(app):
        job = await job_manager.submit(story, JobKind.FULL_GENERATION, lambda: _hold())
        await asyncio.sleep(0)
        assert job_manager.is_running(job.id)

    saved = await job_repo.get(job.id)
    assert (saved.status, saved.error) == (JobStatus.FAILED, INTERRUPTED_ERROR)


# ── Spec-510 T0.4: la estimación y los tiempos viajan en el job ───────────────


async def test_params_llevan_perfil_y_estimacion_sin_pisar_los_del_job(
    manager, job_repo, story_repo, monkeypatch
):
    import src.config as config

    monkeypatch.setattr(config, "_active_profile_name", "perfil-test")
    monkeypatch.setattr(config, "_profile", {"estimated_seconds": {"regenerate_voz": 70}})
    story = await _story(story_repo)

    job = await manager.submit(
        story, JobKind.REGENERATE_VOZ, _quick_run(), params={"beat": 3, "narrative_id": "n-1"}
    )
    await manager.wait(job.id)

    saved = await job_repo.get(job.id)
    assert saved.params == {
        "beat": 3,
        "narrative_id": "n-1",
        "profile": "perfil-test",
        "estimated_seconds": 70,
    }


async def test_payload_trae_tiempos(manager, bus, story_repo):
    story = await _story(story_repo)
    global_q, _ = bus.subscribe(GLOBAL_CHANNEL)

    job = await manager.submit(story, JobKind.FULL_GENERATION, _quick_run(total=1))
    await manager.wait(job.id)

    started, *progress, done = [e.data for e in _drain(global_q)]
    assert (started["started_at"], started["finished_at"], started["elapsed_seconds"]) == (
        None,
        None,
        None,
    )
    assert progress[0]["started_at"] is not None and progress[0]["finished_at"] is None
    assert isinstance(progress[0]["elapsed_seconds"], int)
    assert done["started_at"] == progress[0]["started_at"]
    assert done["finished_at"] is not None and done["elapsed_seconds"] >= 0
    assert done["params"]["estimated_seconds"] > 0


async def test_si_falla_el_estimador_el_job_arranca_igual(bus, job_repo, story_repo):
    class _Broken:
        async def estimate(self, kind, profile):
            raise RuntimeError("sin estimación")

    manager = JobManager(bus, job_repo, story_repo, estimator=_Broken())
    story = await _story(story_repo)

    job = await manager.submit(story, JobKind.FULL_GENERATION, _quick_run())
    await manager.wait(job.id)

    saved = await job_repo.get(job.id)
    assert saved.status == JobStatus.DONE
    assert "estimated_seconds" not in saved.params
