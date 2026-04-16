"""Response schemas."""

from datetime import datetime

from pydantic import BaseModel


class StoryResponse(BaseModel):
    """Response for a story."""

    id: str
    title: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class BeatResponse(BaseModel):
    """Response for a beat."""

    number: int
    summary: str
    content: str = ""
    status: str = "pending"
