"""Request schemas."""

from pydantic import BaseModel, Field


class StoryCreateRequest(BaseModel):
    """Request for creating a story."""

    title: str
    protagonista: str
    relator: str
    escenarios: str
    sinopsis: str
    atmosfera: str
    reglas: list[str] = Field(default_factory=list)


class BeatUpdateRequest(BaseModel):
    """Request for updating a beat."""

    summary: str
