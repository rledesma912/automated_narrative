"""Request schemas."""

from typing import Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field

from src.domain.jobs import JobKind


class StoryCreateRequest(BaseModel):
    """Request for creating a story."""

    title: str
    protagonista: str
    relator: str
    escenarios: str
    sinopsis: str
    genero: str = ""
    subgenero: str = ""
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


class JobCreateRequest(BaseModel):
    """Request para lanzar un job (Spec-460).

    `regenerate_voz` requiere `beat` y `narrative_id` (Spec-430).
    """

    kind: JobKind = JobKind.FULL_GENERATION
    beat: int | None = None
    narrative_id: UUID | None = None
