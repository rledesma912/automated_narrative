"""Jobs de generación asíncrona (Spec-460).

Un job es una ejecución de trabajo LLM (generación completa o regeneración de
un acto) que corre en background, desacoplada de cualquier conexión HTTP.
"""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import UUID4, BaseModel, Field

from src.utils.timezone import now_argentina


class JobKind(str, Enum):
    """Tipo de trabajo."""

    FULL_GENERATION = "full_generation"
    REGENERATE_VOZ = "regenerate_voz"


class JobStatus(str, Enum):
    """Ciclo de vida: queued → running → done | failed."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


ACTIVE_JOB_STATUSES = (JobStatus.QUEUED, JobStatus.RUNNING)


class JobStage(str, Enum):
    """Etapa del pipeline en la que está el job."""

    ANALYST = "analyst"
    RESOLVER = "resolver"
    MAPPER = "mapper"
    VOZ = "voz"
    JOURNAL = "journal"
    CONSOLIDANDO = "consolidando"


class Job(BaseModel):
    """Ejecución de un trabajo de generación sobre una historia."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    story_id: UUID4
    kind: JobKind
    status: JobStatus = JobStatus.QUEUED
    stage: JobStage | None = None
    beat: int | None = None
    total_beats: int | None = None
    params: dict = Field(default_factory=dict)
    error: str | None = None
    narrative_id: UUID4 | None = None
    created_at: datetime = Field(default_factory=now_argentina)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_JOB_STATUSES
