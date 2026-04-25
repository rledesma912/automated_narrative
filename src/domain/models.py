"""Domain entities."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import UUID4, BaseModel, Field


class StoryStatus(str, Enum):
    """Estado de una historia."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class NarrativeAnchors(BaseModel):
    """Anclajes narrativos extraídos una vez de la sinopsis global (Spec 038)."""

    story_id: UUID4
    initial_state: str
    threat_nature: str
    horror_peak: str
    spatial_anchor: str


class Scenario(BaseModel):
    """Escenario cronológico de la historia (Spec 038)."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    story_id: UUID4
    order_index: int
    name: str


class MacroBeat(BaseModel):
    """Unidad narrativa estructural (acto)."""

    number: int
    summary: str
    content: str = ""
    status: str = "pending"
    technical_context: Optional[list[int]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    # Spec 038: campos nuevos
    active_scenario_id: Optional[str] = None
    active_rules: list[str] = []
    active_scenario_description: str = ""
    narrative_context: Optional[str] = None
    memory_snapshot: Optional[str] = None


# Alias de compatibilidad — se mantiene mientras los tests y repos migran a MacroBeat
Beat = MacroBeat


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
    sinopsis: str
    atmosfera: str
    reglas: list[str] = []
    beats: list[Beat] = []
    scenarios: list[Scenario] = []
    journal: NarrativeJournal = Field(default_factory=NarrativeJournal)
    status: StoryStatus = StoryStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)

    narrative_brief: str = ""

    protagonist: str = ""  # English mapping
    atmosphere: str = ""   # English mapping
    synopsis: str = ""     # English mapping


def resolve_beat_anchors(
    anchors: NarrativeAnchors,
    macro_beat_id: int,
    beats_spec: list[dict],
) -> dict:
    """Retorna los valores de anclaje principal y contexto para un macro-beat.

    Determinístico: lee anchor_priorities del YAML, no llama al LLM.
    """
    beat_spec = next((b for b in beats_spec if b["id"] == macro_beat_id), None)
    if not beat_spec:
        return {}
    priorities = beat_spec.get("anchor_priorities", {})
    return {
        "principal": getattr(anchors, priorities.get("principal", ""), ""),
        "contexto": getattr(anchors, priorities.get("contexto", ""), ""),
    }
