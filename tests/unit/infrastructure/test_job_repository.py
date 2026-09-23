"""Tests de SQLJobRepository (Spec-460 T1.3, T1.4)."""

import sqlite3
import uuid
from datetime import timedelta

import pytest

from src.config import settings
from src.domain.jobs import Job, JobKind, JobStage, JobStatus
from src.infrastructure.database.connection import get_connection, init_db
from src.infrastructure.database.repositories.job_repository import (
    INTERRUPTED_ERROR,
    SQLJobRepository,
)
from src.utils.timezone import now_argentina


@pytest.fixture
async def repo(monkeypatch, tmp_path) -> SQLJobRepository:
    """Repo sobre una DB temporal recién inicializada (pytest borra `tmp_path`)."""
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    await init_db()
    return SQLJobRepository()


async def _story(title: str = "t") -> uuid.UUID:
    story_id = uuid.uuid4()
    conn = await get_connection()
    await conn.execute("INSERT INTO story (id, title) VALUES (?, ?)", (str(story_id), title))
    await conn.commit()
    await conn.close()
    return story_id


def _job(story_id: uuid.UUID, **kw) -> Job:
    return Job(story_id=story_id, kind=kw.pop("kind", JobKind.FULL_GENERATION), **kw)


async def test_create_y_get_round_trip(repo: SQLJobRepository):
    story_id = await _story()
    narrative_id = uuid.uuid4()
    job = _job(
        story_id,
        kind=JobKind.REGENERATE_VOZ,
        total_beats=5,
        params={"beat": 3, "narrative_id": str(narrative_id)},
    )

    await repo.create(job)
    loaded = await repo.get(job.id)

    assert loaded == job


async def test_get_inexistente_devuelve_none(repo: SQLJobRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_ciclo_de_vida_completo(repo: SQLJobRepository):
    story_id = await _story()
    job = await repo.create(_job(story_id, total_beats=5))
    narrative_id = uuid.uuid4()

    await repo.mark_running(job.id)
    await repo.update_progress(job.id, JobStage.VOZ, 3)
    running = await repo.get(job.id)
    assert running.status == JobStatus.RUNNING
    assert running.started_at is not None
    assert (running.stage, running.beat) == (JobStage.VOZ, 3)

    await repo.finish(job.id, JobStatus.DONE, narrative_id=narrative_id)
    done = await repo.get(job.id)
    assert done.status == JobStatus.DONE
    assert done.narrative_id == narrative_id
    assert done.finished_at is not None
    assert not done.is_active


async def test_finish_failed_guarda_el_error(repo: SQLJobRepository):
    job = await repo.create(_job(await _story()))

    await repo.finish(job.id, JobStatus.FAILED, error="cancelada por el usuario")

    failed = await repo.get(job.id)
    assert (failed.status, failed.error) == (JobStatus.FAILED, "cancelada por el usuario")


async def test_segundo_job_activo_para_la_misma_historia_se_rechaza(repo: SQLJobRepository):
    story_id = await _story()
    await repo.create(_job(story_id))

    with pytest.raises(sqlite3.IntegrityError):
        await repo.create(_job(story_id))


async def test_job_nuevo_permitido_cuando_el_anterior_termino(repo: SQLJobRepository):
    story_id = await _story()
    first = await repo.create(_job(story_id))
    await repo.finish(first.id, JobStatus.DONE)

    second = await repo.create(_job(story_id))

    assert (await repo.get_active_for_story(story_id)).id == second.id


async def test_get_active_for_story(repo: SQLJobRepository):
    story_a, story_b = await _story("a"), await _story("b")
    job_a = await repo.create(_job(story_a))

    assert (await repo.get_active_for_story(story_a)).id == job_a.id
    assert await repo.get_active_for_story(story_b) is None


async def test_list_active_y_list_recent(repo: SQLJobRepository):
    story_a, story_b, story_c = await _story("a"), await _story("b"), await _story("c")
    antes = now_argentina() - timedelta(seconds=1)
    activo = await repo.create(_job(story_a))
    terminado = await repo.create(_job(story_b))
    await repo.finish(terminado.id, JobStatus.DONE)
    viejo = await repo.create(_job(story_c))
    await repo.finish(viejo.id, JobStatus.FAILED)

    assert [j.id for j in await repo.list_active()] == [activo.id]
    recientes = {j.id for j in await repo.list_recent(since=antes)}
    assert recientes == {terminado.id, viejo.id}
    assert await repo.list_recent(since=now_argentina() + timedelta(seconds=1)) == []


async def test_recover_interrupted_marca_failed_solo_los_activos(repo: SQLJobRepository):
    story_a, story_b, story_c = await _story("a"), await _story("b"), await _story("c")
    queued = await repo.create(_job(story_a))
    running = await repo.create(_job(story_b))
    await repo.mark_running(running.id)
    done = await repo.create(_job(story_c))
    await repo.finish(done.id, JobStatus.DONE)

    count = await repo.recover_interrupted()

    assert count == 2
    for job_id in (queued.id, running.id):
        job = await repo.get(job_id)
        assert (job.status, job.error) == (JobStatus.FAILED, INTERRUPTED_ERROR)
        assert job.finished_at is not None
    assert (await repo.get(done.id)).status == JobStatus.DONE
    assert await repo.recover_interrupted() == 0


async def test_borrar_la_historia_borra_sus_jobs(repo: SQLJobRepository):
    story_id = await _story()
    job = await repo.create(_job(story_id))

    conn = await get_connection()
    await conn.execute("DELETE FROM story WHERE id = ?", (str(story_id),))
    await conn.commit()
    await conn.close()

    assert await repo.get(job.id) is None


async def test_arranque_de_la_app_recupera_jobs_interrumpidos(repo: SQLJobRepository):
    """T1.4: el lifespan de FastAPI llama a recover_interrupted()."""
    from src.main import app, lifespan

    job = await repo.create(_job(await _story()))
    await repo.mark_running(job.id)

    async with lifespan(app):
        pass

    recovered = await repo.get(job.id)
    assert (recovered.status, recovered.error) == (JobStatus.FAILED, INTERRUPTED_ERROR)
