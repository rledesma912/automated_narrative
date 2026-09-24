"""Spec-510 T0.3: JobDurationEstimator."""

import uuid
from datetime import timedelta

import pytest

from src.application.services.job_duration_estimator import JobDurationEstimator
from src.domain.jobs import Job, JobKind, JobStatus
from src.utils.timezone import now_argentina

PROFILE = "ollama-gemma3-12b"


def _job(seconds: float | None, profile: str | None = PROFILE, kind=JobKind.FULL_GENERATION):
    start = now_argentina()
    return Job(
        story_id=uuid.uuid4(),
        kind=kind,
        status=JobStatus.DONE,
        params={"profile": profile} if profile else {},
        started_at=start,
        finished_at=start + timedelta(seconds=seconds) if seconds is not None else None,
    )


class FakeJobs:
    def __init__(self, jobs: list[Job]):
        self.jobs = jobs
        self.calls: list[JobKind] = []

    async def list_finished(self, kind: JobKind, limit: int = 50) -> list[Job]:
        self.calls.append(kind)
        return [j for j in self.jobs if j.kind == kind][:limit]


@pytest.fixture(autouse=True)
def _default_estimates(monkeypatch):
    import src.config as config

    monkeypatch.setattr(
        config, "_profile", {"estimated_seconds": {"full_generation": 230, "regenerate_voz": 50}}
    )


async def _estimate(jobs: list[Job], kind=JobKind.FULL_GENERATION):
    return await JobDurationEstimator(FakeJobs(jobs)).estimate(kind, PROFILE)


async def test_sin_historial_usa_el_valor_inicial():
    estimate = await _estimate([])
    assert (estimate.seconds, estimate.source, estimate.samples) == (230, "default", 0)


async def test_una_muestra_no_alcanza():
    estimate = await _estimate([_job(300)])
    assert (estimate.seconds, estimate.source, estimate.samples) == (230, "default", 1)


async def test_dos_muestras_mediana_par():
    estimate = await _estimate([_job(200), _job(221)])
    assert (estimate.seconds, estimate.source, estimate.samples) == (210, "history", 2)


async def test_mediana_de_las_ultimas_cinco():
    # list_finished ya viene del más nuevo al más viejo: los 2 últimos quedan afuera.
    jobs = [_job(s) for s in (210, 200, 250, 220, 230, 999, 999)]
    estimate = await _estimate(jobs)
    assert (estimate.seconds, estimate.source, estimate.samples) == (220, "history", 5)


async def test_filtra_por_perfil_y_descarta_sin_perfil():
    jobs = [_job(100, profile="otro"), _job(100, profile=None), _job(200), _job(240)]
    estimate = await _estimate(jobs)
    assert (estimate.seconds, estimate.samples) == (220, 2)


async def test_descarta_corridas_del_mock_y_sin_fin():
    jobs = [_job(0.2), _job(4.9), _job(None), _job(200)]
    estimate = await _estimate(jobs)
    assert (estimate.source, estimate.samples) == ("default", 1)


async def test_por_tipo_de_job():
    jobs = [_job(300), _job(300), _job(45, kind=JobKind.REGENERATE_VOZ)]
    estimate = await _estimate(jobs, kind=JobKind.REGENERATE_VOZ)
    assert (estimate.seconds, estimate.source, estimate.samples) == (50, "default", 1)


async def test_as_dict():
    estimate = await _estimate([])
    assert estimate.as_dict() == {"seconds": 230, "source": "default", "samples": 0}
