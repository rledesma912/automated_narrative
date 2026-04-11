from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from src.domain.models import StoryStatus

class ActInputSchema(BaseModel):
    number: int
    title: str
    mission: str

class GenerateStoryRequest(BaseModel):
    title: str
    protagonistas: str
    relator: str
    escenarios: str
    sinopsis: str
    atmosfera: str
    reglas: List[str] = []
    actos_input: List[ActInputSchema]

class StoryResponse(BaseModel):
    id: UUID
    title: str
    status: StoryStatus
    created_at: datetime

    class Config:
        from_attributes = True

class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    current_act: int
    total_acts: int
    message: Optional[str] = None
