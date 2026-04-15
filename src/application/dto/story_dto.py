"""Story DTOs."""

from pydantic import BaseModel
from uuid import UUID


class StoryCreateDTO(BaseModel):
    """DTO for creating a story."""

    title: str
    protagonista: str
    relator: str
    escenarios: str
    sinopsis: str
    atmosfera: str
    reglas: list[str] = []


class StoryResponseDTO(BaseModel):
    """DTO for story response."""

    id: UUID
    title: str
    status: str
    created_at: str

    class Config:
        from_attributes = True
