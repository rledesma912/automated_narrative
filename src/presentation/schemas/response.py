"""Response schemas."""

from datetime import datetime

from pydantic import BaseModel


class StoryResponse(BaseModel):
    """Response for a story."""

    id: str
    title: str
    status: str
    created_at: datetime
    genero: str | None = None
    subgenero: str | None = None
    tono: str | None = None
    protagonista: str | None = None
    relator: str | None = None
    sinopsis: str | None = None
    narrator_config: dict | None = None
    personajes_full: list | None = None

    class Config:
        from_attributes = True


class BeatResponse(BaseModel):
    """Response for a beat."""

    number: int
    summary: str
    content: str = ""
    status: str = "pending"


class BeatRegenerateResponse(BaseModel):
    """Response tras regenerar la Voz de un beat (Spec-430)."""

    beat: BeatResponse
    narrative_id: str
    narrative_content: str


class GeneratedNarrativeResponse(BaseModel):
    """Response for a generated narrative."""

    id: str
    story_template_id: str
    title: str
    content: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


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
