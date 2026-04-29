"""Response schemas."""

from datetime import datetime

from pydantic import BaseModel


class StoryResponse(BaseModel):
    """Response for a story."""

    id: str
    title: str
    status: str
    created_at: datetime
    atmosfera: str | None = None
    protagonista: str | None = None
    relator: str | None = None
    sinopsis: str | None = None
    storyteller_config: dict | None = None
    personajes_full: list | None = None

    class Config:
        from_attributes = True


class BeatResponse(BaseModel):
    """Response for a beat."""

    number: int
    summary: str
    content: str = ""
    status: str = "pending"
