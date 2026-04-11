import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field


class StoryStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ActInput(BaseModel):
    number: int
    title: str
    mission: str

class NarrativeState(BaseModel):
    location: str = ""
    characters: str = ""
    situation: str = ""
    active_threat: str = ""
    goal: str = ""
    last_action: str = ""

class GeneratedAct(BaseModel):
    number: int
    content: str
    raw_output: str
    word_count: int
    state_after: Optional[NarrativeState] = None
    created_at: datetime = Field(default_factory=datetime.now)

class Story(BaseModel):
    id: UUID4 = Field(default_factory=uuid.uuid4)
    title: str
    protagonistas: str
    relator: str
    escenarios: str
    sinopsis: str
    atmosfera: str
    reglas: List[str] = []
    actos_input: List[ActInput] = []
    status: StoryStatus = StoryStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
