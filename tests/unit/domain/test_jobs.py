"""Tests del modelo de dominio Job (Spec-460 T1.1)."""

import uuid

import pytest
from pydantic import ValidationError

from src.domain.jobs import Job, JobKind, JobStage, JobStatus


def test_job_nuevo_arranca_en_queued_y_activo():
    job = Job(story_id=uuid.uuid4(), kind=JobKind.FULL_GENERATION)

    assert job.status == JobStatus.QUEUED
    assert job.is_active
    assert job.stage is None and job.beat is None
    assert job.params == {}
    assert job.created_at.tzinfo is not None


@pytest.mark.parametrize(
    ("status", "activo"),
    [
        (JobStatus.QUEUED, True),
        (JobStatus.RUNNING, True),
        (JobStatus.DONE, False),
        (JobStatus.FAILED, False),
    ],
)
def test_is_active_segun_estado(status, activo):
    job = Job(story_id=uuid.uuid4(), kind=JobKind.FULL_GENERATION, status=status)

    assert job.is_active is activo


def test_ids_unicos_por_job():
    story_id = uuid.uuid4()

    assert (
        Job(story_id=story_id, kind="full_generation").id
        != Job(story_id=story_id, kind="full_generation").id
    )


def test_acepta_valores_string_de_los_enums():
    job = Job(
        story_id=uuid.uuid4(),
        kind="regenerate_voz",
        status="running",
        stage="voz",
        beat=3,
        params={"beat": 3, "narrative_id": str(uuid.uuid4())},
    )

    assert job.kind == JobKind.REGENERATE_VOZ
    assert job.stage == JobStage.VOZ


def test_rechaza_kind_desconocido():
    with pytest.raises(ValidationError):
        Job(story_id=uuid.uuid4(), kind="otro")
