"""Domain entities."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import UUID4, BaseModel, Field
import uuid


class StoryStatus(str, Enum):
    """Estado de una historia."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Beat(BaseModel):
    """Unidad mínima de narración."""

    number: int
    summary: str
    content: str = ""
    status: str = "pending"
    technical_context: Optional[list[int]] = None
    created_at: datetime = Field(default_factory=datetime.now)


class NarrativeJournal(BaseModel):
    """Memoria narrativa para coherencia."""

    last_events: str = ""
    unresolved_mysteries: str = ""
    physical_emotional_state: str = ""


class StoryPlan(BaseModel):
    """Plan maestro de la historia."""

    story_id: UUID4
    title: str
    beats: list[Beat] = []
    created_at: datetime = Field(default_factory=datetime.now)


class Story(BaseModel):
    """Historia base."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    title: str
    protagonista: str
    relator: str
    escenarios: str
    sinopsis: str
    atmosfera: str
    reglas: list[str] = []
    beats: list[Beat] = []
    journal: NarrativeJournal = Field(default_factory=NarrativeJournal)
    status: StoryStatus = StoryStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
