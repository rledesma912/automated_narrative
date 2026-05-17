"""Domain entities."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import UUID4, BaseModel, Field, field_validator

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
    """Categoría semántica de una regla narrativa (Spec-043).

    Spec-190 §4.4: lo temporal (eventos, acciones de personaje) no es regla —
    va en `macro_beat.synopsis_beat`. Quedan las categorías estables.
    """

    PSICOLOGICA = "psicologica"
    ENTORNO = "entorno"
    FENOMENO = "fenomeno"
    INDICADOR = "indicador"


class TypedRule(BaseModel):
    """Regla narrativa con semántica explícita (Spec-043).

    Spec-190 §4.4: `applies_to_beat` define el alcance — `None` = regla global
    (aplica a los 5 actos); `1..N` = regla anclada a ese acto.
    """

    id: str
    story_id: UUID4
    content: str
    type: Optional[RuleType] = None
    intensity: Optional[str] = None
    applies_to_beat: Optional[int] = None


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
    description: str = ""


class MacroBeat(BaseModel):
    """Unidad narrativa estructural (acto)."""

    number: int
    summary: str
    generated_act: str = ""
    status: BeatStatus = BeatStatus.PENDING
    created_at: datetime = Field(default_factory=now_argentina)
    # Spec 038: campos nuevos
    active_scenario_id: Optional[str] = None
    active_scenario_description: str = ""
    user_prompt: Optional[str] = None
    beat_type: Optional[BeatType] = None
    # Spec 190 (Slice 3): trazabilidad de prompting + input del usuario
    system_prompt: Optional[str] = None
    synopsis_beat: Optional[str] = None

    def is_narrated(self) -> bool:
        """True si el beat tiene prosa generada y está marcado como completado."""
        return bool(self.generated_act and self.status == BeatStatus.COMPLETED)

    def is_pending(self) -> bool:
        """True si el beat aún no fue narrado."""
        return self.status == BeatStatus.PENDING

    def has_content(self) -> bool:
        """True si el beat tiene contenido (independientemente del status)."""
        return bool(self.generated_act)


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


class StoryMetadata(BaseModel):
    """Value object con los datos de input del usuario (Spec 080)."""

    protagonista: str
    relator: str
    sinopsis: str
    genero: str = ""
    subgenero: str = ""
    tono: str = ""
    reglas: list[str] = []
    narrator_config: Optional[dict] = None
    personajes_full: list[dict] = []

    @classmethod
    def from_story(cls, story: "Story") -> "StoryMetadata":
        return cls(
            protagonista=story.protagonista,
            relator=story.relator,
            sinopsis=story.sinopsis,
            genero=story.genero,
            subgenero=story.subgenero,
            tono=story.tono,
            reglas=story.reglas,
            narrator_config=story.narrator_config,
            personajes_full=story.personajes_full,
        )

    def has_rules(self) -> bool:
        """True si hay reglas de narrativa o configuración de narrador."""
        return bool(self.reglas or self.narrator_config)


class GeneratedNarrative(BaseModel):
    """Variante narrativa generada a partir de una StoryTemplate."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    story_template_id: UUID4
    title: str
    content: str
    status: StoryStatus = StoryStatus.COMPLETED
    created_at: datetime = Field(default_factory=now_argentina)


class Story(BaseModel):
    """Historia base."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    title: str = Field(..., min_length=1)
    protagonista: str = Field(..., min_length=1)
    relator: str = Field(..., min_length=1)
    sinopsis: str = Field(..., min_length=1)
    genero: str = ""
    subgenero: str = ""
    tono: str = ""
    reglas: list[str] = []
    beats: list[Beat] = []
    scenarios: list[Scenario] = []
    journal: NarrativeJournal = Field(default_factory=NarrativeJournal)
    status: StoryStatus = StoryStatus.DRAFT
    created_at: datetime = Field(default_factory=now_argentina)

    narrator_config: Optional[dict] = None
    typed_rules: list[TypedRule] = []
    personajes_full: list[dict] = []

    @field_validator("title", "protagonista", "relator", "sinopsis", mode="before")
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @property
    def atmosfera(self) -> str:
        """String de atmósfera derivado de genero/subgenero/tono (Spec-190 §T6.3).

        Formato: `genero (subgenero) - tono`. Sustituye a la columna `atmosfera`
        eliminada; los prompts que necesitan un único string lo consumen por acá.
        """
        genero = self.genero or ""
        subgenero = f" ({self.subgenero})" if self.subgenero else ""
        tono = f" - {self.tono}" if self.tono else ""
        return f"{genero}{subgenero}{tono}".strip()

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

    def active_rules_for_beat(self, beat_number: int) -> list[str]:
        """Reglas activas de un beat, derivadas determinísticamente (Spec-190 §4.4).

        Una regla aplica al beat N si es global (`applies_to_beat is None`) o está
        anclada exactamente a ese acto (`applies_to_beat == N`). Si la historia no
        tiene `typed_rules`, se cae a `reglas` (strings legacy), todas globales.
        """
        if self.typed_rules:
            return [
                r.content
                for r in self.typed_rules
                if r.applies_to_beat is None or r.applies_to_beat == beat_number
            ]
        return list(self.reglas)

    def get_beat_by_number(self, n: int) -> Beat | None:
        """Retorna el beat con ese número, o None si no existe."""
        return next((b for b in self.beats if b.number == n), None)

    def get_first_beat(self) -> Beat | None:
        """Retorna el primer beat (menor número), o None si no hay beats."""
        return min(self.beats, key=lambda b: b.number) if self.beats else None

    def get_last_beat(self) -> Beat | None:
        """Retorna el último beat (mayor número), o None si no hay beats."""
        return max(self.beats, key=lambda b: b.number) if self.beats else None
