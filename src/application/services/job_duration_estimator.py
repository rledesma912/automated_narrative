"""Duración estimada de un job de generación (Spec-510 §2.1).

Mediana de las últimas duraciones reales del mismo tipo y el mismo perfil LLM;
sin historial suficiente, el valor inicial del perfil
(`settings.estimated_seconds`).
"""

from dataclasses import dataclass
from statistics import median
from typing import Protocol

from src.config import settings
from src.domain.jobs import Job, JobKind

SAMPLE_SIZE = 5
MIN_SAMPLES = 2
# Las corridas con el LLM mock (E2E, --mock) terminan en milisegundos.
MIN_VALID_SECONDS = 5


class FinishedJobs(Protocol):
    async def list_finished(self, kind: JobKind, limit: int = 50) -> list[Job]: ...


@dataclass(frozen=True)
class Estimate:
    seconds: int
    source: str  # "history" | "default"
    samples: int

    def as_dict(self) -> dict:
        return {"seconds": self.seconds, "source": self.source, "samples": self.samples}


class JobDurationEstimator:
    def __init__(self, jobs: FinishedJobs):
        self._jobs = jobs

    async def estimate(self, kind: JobKind, profile: str) -> Estimate:
        durations = [
            seconds
            for job in await self._jobs.list_finished(kind)
            if job.params.get("profile") == profile
            and (seconds := _duration(job)) is not None
            and seconds >= MIN_VALID_SECONDS
        ][:SAMPLE_SIZE]
        if len(durations) < MIN_SAMPLES:
            return Estimate(settings.estimated_seconds(kind.value), "default", len(durations))
        return Estimate(round(median(durations)), "history", len(durations))


def _duration(job: Job) -> float | None:
    if not job.started_at or not job.finished_at:
        return None
    return (job.finished_at - job.started_at).total_seconds()
