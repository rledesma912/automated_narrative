"""Beat DTOs."""

from pydantic import BaseModel


class BeatCreateDTO(BaseModel):
    """DTO for creating a beat (empty, just the number)."""

    number: int
    summary: str


class BeatResponseDTO(BaseModel):
    """DTO for beat response."""

    number: int
    summary: str
    content: str = ""
    status: str = "pending"
