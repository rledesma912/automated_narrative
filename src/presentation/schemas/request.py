"""Request schemas."""

from typing import Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field


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
    # El wizard web lo envía como `storyteller_config` (mismo nombre que el YAML).
    narrator_config: Optional[dict] = Field(
        default=None,
        validation_alias=AliasChoices("narrator_config", "storyteller_config"),
    )
    personajes_full: list[dict] = Field(default_factory=list)


class BeatUpdateRequest(BaseModel):
    """Request for updating a beat."""

    summary: str


class BeatRegenerateRequest(BaseModel):
    """Request para regenerar solo la Voz de un beat (Spec-430)."""

    narrative_id: UUID
