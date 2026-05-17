"""Request schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class StoryCreateRequest(BaseModel):
    """Request for creating a story."""

    title: str
    protagonista: str
    relator: str
    escenarios: str
    sinopsis: str
    genero: str = ""
    subgenero: str = ""
    tono: str = ""
    reglas: list[str] = Field(default_factory=list)
    narrator_config: Optional[dict] = None
    personajes_full: list[dict] = Field(default_factory=list)


class BeatUpdateRequest(BaseModel):
    """Request for updating a beat."""

    summary: str
