"""Domain entities."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import UUID4, BaseModel, Field

from src.utils.timezone import now_argentina


class StoryStatus(str, Enum):
    """Estado de una historia."""

    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BeatType(str, Enum):
    """Función narrativa de un macro-beat (Spec-043)."""

    EXPOSICION = "exposicion"
    ACCION_ASCENDENTE = "accion_ascendente"
    CLIMAX = "climax"
    ACCION_DESCENDENTE = "accion_descendente"
    DESENLACE = "desenlace"


class BeatStatus(str, Enum):
    """Estado del ciclo de vida de un macro-beat (Spec-250)."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class RuleType(str, Enum):
    """Categoría semántica de una regla narrativa (Spec-043)."""

    PSICOLOGICA = "psicologica"
    ENTORNO = "entorno"
    EVENTO = "evento"
    FENOMENO = "fenomeno"
    ACCION_PERSONAJE = "accion_personaje"
    INDICADOR = "indicador"


class TypedRule(BaseModel):
    """Regla narrativa con semántica explícita (Spec-043)."""

    id: str
    story_id: UUID4
    content: str
    type: Optional[RuleType] = None
    intensity: Optional[str] = None


class NarrativeAnchors(BaseModel):
    """Anclajes de resonancia narrativa extraídos de la sinopsis global (Spec 081)."""

    story_id: UUID4
    resonance_hamartia: str  # La Grieta (Acto 1)
    resonance_hybris: str  # La Transgresión (Acto 2)
    resonance_anagnorisis: str  # La Epifanía (Acto 3)
    resonance_peripeteia: str  # La Claustrofobia (Acto 4)
    resonance_residual: str  # La Mancha (Acto 5)


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
    status: BeatStatus = BeatStatus.PENDING
    created_at: datetime = Field(default_factory=now_argentina)
    # Spec 038: campos nuevos
    active_scenario_id: Optional[str] = None
    active_rules: list[str] = []
    active_scenario_description: str = ""
    narrative_context: Optional[str] = None
    beat_type: Optional[BeatType] = None

    def is_narrated(self) -> bool:
        """True si el beat tiene prosa generada y está marcado como completado."""
        return bool(self.content and self.status == BeatStatus.COMPLETED)

    def is_pending(self) -> bool:
        """True si el beat aún no fue narrado."""
        return self.status == BeatStatus.PENDING

    def has_content(self) -> bool:
        """True si el beat tiene contenido (independientemente del status)."""
        return bool(self.content)


# Alias de compatibilidad — se mantiene mientras los tests y repos migran a MacroBeat
Beat = MacroBeat


class NarrativeJournal(BaseModel):
    """Memoria narrativa para coherencia."""

    last_events: str = ""
    unresolved_mysteries: str = ""
    physical_emotional_state: str = ""

    def is_empty(self) -> bool:
        """True si no tiene ningún campo con datos."""
        return not (self.last_events or self.unresolved_mysteries or self.physical_emotional_state)


class StoryPlan(BaseModel):
    """Plan maestro de la historia."""

    story_id: UUID4
    title: str
    beats: list[Beat] = []
    created_at: datetime = Field(default_factory=now_argentina)


class StoryMetadata(BaseModel):
    """Value object con los datos de input del usuario (Spec 080)."""

    protagonista: str
    relator: str
    sinopsis: str
    atmosfera: str
    reglas: list[str] = []
    storyteller_config: Optional[dict] = None
    personajes_full: list[dict] = []

    @classmethod
    def from_story(cls, story: "Story") -> "StoryMetadata":
        return cls(
            protagonista=story.protagonista,
            relator=story.relator,
            sinopsis=story.sinopsis,
            atmosfera=story.atmosfera,
            reglas=story.reglas,
            storyteller_config=story.storyteller_config,
            personajes_full=story.personajes_full,
        )

    def has_rules(self) -> bool:
        """True si hay reglas de narrativa o configuración de narrador."""
        return bool(self.reglas or self.storyteller_config)


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
    status: StoryStatus = StoryStatus.DRAFT
    created_at: datetime = Field(default_factory=now_argentina)

    narrative_brief: str = ""
    storyteller_config: Optional[dict] = None
    typed_rules: list[TypedRule] = []
    personajes_full: list[dict] = []
    file_path: Optional[str] = None

    # -- Spec 070: comportamiento de dominio --

    def has_beats(self) -> bool:
        """True si la historia tiene al menos un beat."""
        return bool(self.beats)

    def beat_count(self) -> int:
        """Número de beats de la historia."""
        return len(self.beats)

    def get_pending_beats(self) -> list[Beat]:
        """Retorna los beats que aún no fueron narrados."""
        return [b for b in self.beats if b.is_pending()]

    def get_completed_beats(self) -> list[Beat]:
        """Retorna los beats completamente narrados."""
        return [b for b in self.beats if b.is_narrated()]

    # -- Spec 080: aggregate root --

    @property
    def metadata(self) -> StoryMetadata:
        """Value object con los datos de input del usuario."""
        return StoryMetadata.from_story(self)

    @property
    def has_content(self) -> bool:
        """True si al menos un beat tiene prosa generada."""
        return bool(self.beats) and any(b.has_content() for b in self.beats)

    def get_beat_by_number(self, n: int) -> Beat | None:
        """Retorna el beat con ese número, o None si no existe."""
        return next((b for b in self.beats if b.number == n), None)

    def get_first_beat(self) -> Beat | None:
        """Retorna el primer beat (menor número), o None si no hay beats."""
        return min(self.beats, key=lambda b: b.number) if self.beats else None

    def get_last_beat(self) -> Beat | None:
        """Retorna el último beat (mayor número), o None si no hay beats."""
        return max(self.beats, key=lambda b: b.number) if self.beats else None
