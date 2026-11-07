"""Duración estimada de un job de generación (Spec-510 §2.1).

Mediana de las últimas duraciones reales del mismo tipo y el mismo perfil LLM;
sin historial suficiente, el valor inicial del perfil
(`settings.estimated_seconds`).

Spec-650: el relato completo tarda según su largo; su mediana se calcula aparte por
estructura (jobs viejos sin `structure` en `params` = medio, Spec-750). Sin historial de
otro largo, el valor inicial es el del perfil (`full_generation_corto`, `…_largo`) o el de
la media en proporción a las palabras del relato (Spec-750; antes, a los actos).
"""

import re
from dataclasses import dataclass
from statistics import median
from typing import Protocol

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.structure import DEFAULT_STRUCTURE
from src.config import settings
from src.domain.jobs import Job, JobKind

SAMPLE_SIZE = 5
MIN_SAMPLES = 2
# Las corridas con el LLM mock (E2E, --mock) terminan en milisegundos.
MIN_VALID_SECONDS = 5
# Spec-650: tipos de job cuya duración depende del largo del relato.
BY_STRUCTURE = frozenset({JobKind.FULL_GENERATION})


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

    async def estimate(
        self, kind: JobKind, profile: str, structure: str = DEFAULT_STRUCTURE
    ) -> Estimate:
        if kind not in BY_STRUCTURE:
            structure = DEFAULT_STRUCTURE
        durations = [
            seconds
            for job in await self._jobs.list_finished(kind)
            if job.params.get("profile") == profile
            and (kind not in BY_STRUCTURE or _structure(job) == structure)
            and (seconds := _duration(job)) is not None
            and seconds >= MIN_VALID_SECONDS
        ][:SAMPLE_SIZE]
        if len(durations) < MIN_SAMPLES:
            return Estimate(_default(kind, structure), "default", len(durations))
        return Estimate(round(median(durations)), "history", len(durations))


def _structure(job: Job) -> str:
    return job.params.get("structure") or DEFAULT_STRUCTURE


def _default(kind: JobKind, structure: str) -> int:
    base = settings.estimated_seconds(kind.value)
    if structure == DEFAULT_STRUCTURE:
        return base
    own = (settings.active_profile_config().get("estimated_seconds") or {}).get(
        f"{kind.value}_{structure}"
    )
    if isinstance(own, int | float) and not isinstance(own, bool) and own > 0:
        return int(own)
    # Spec-750: en proporción al texto que lleva (`palabras_total`), no a la cantidad de
    # actos: la media y la larga tienen los mismos actos y la larga tarda más del doble.
    repo = BeatSpecRepository()
    return round(base * _words(repo.estructura(structure)) / _words(repo.estructura()))


def _words(estructura) -> int:
    """`palabras_total` («2.500») como número."""
    return int(re.sub(r"\D", "", estructura.palabras_total) or 1)


def _duration(job: Job) -> float | None:
    if not job.started_at or not job.finished_at:
        return None
    return (job.finished_at - job.started_at).total_seconds()
