"""Response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StoryResponse(BaseModel):
    """Response for a story."""

    id: str
    title: str
    status: str
    created_at: datetime
    genero: str | None = None
    subgenero: str | None = None
    protagonista: str | None = None
    relator: str | None = None
    sinopsis: str | None = None
    narrator_config: dict | None = None
    # Spec-440 §8: vista de autoría completa (atmósfera, escenarios, reglas, actos,
    # narrador) para rehidratar el wizard al editar. Solo en GET /stories/{id}.
    storyteller_config: dict | None = None
    personajes_full: list | None = None
    # Spec-530: la historia se armó con el asistente (se edita ahí, no en el wizard).
    authoring: bool = False

    model_config = ConfigDict(from_attributes=True)


class BeatResponse(BaseModel):
    """Response for a beat."""

    number: int
    summary: str
    content: str = ""
    status: str = "pending"


class GeneratedNarrativeResponse(BaseModel):
    """Response for a generated narrative."""

    id: str
    story_template_id: str
    title: str
    content: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    """Estado de un job de generación (Spec-460)."""

    job_id: str
    story_id: str
    kind: str
    status: str
    stage: str | None = None
    beat: int | None = None
    total_beats: int | None = None
    error: str | None = None
    narrative_id: str | None = None
    # Spec-510: tiempos y estimación (en `params`: profile, estimated_seconds).
    params: dict = {}
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: int | None = None
