"""Domain entities."""

import re
import unicodedata
import uuid
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import UUID4, BaseModel, Field, field_validator, model_validator

from src.utils.timezone import now_argentina


class StoryStatus(str, Enum):
    """Estado de una historia."""

    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BeatStatus(str, Enum):
    """Estado del ciclo de vida de un macro-beat (Spec-250)."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Subgenre(BaseModel):
    """Subgénero del catálogo (Spec-440 §2). El id se repite entre géneros (`otro`)."""

    id: str
    label: str


class EntityNature(BaseModel):
    """Naturaleza de una entidad narrativa: espíritu, culto, criatura… (Spec-450 §1)."""

    id: str
    label: str


class Genre(BaseModel):
    """Género del catálogo con sus subgéneros y las naturalezas de entidad que admite,
    ambos ordenados (Spec-440 §2, Spec-450 §1)."""

    id: str
    label: str
    subgenres: list[Subgenre] = Field(default_factory=list)
    entity_natures: list[EntityNature] = Field(default_factory=list)


class RevealLevel(str, Enum):
    """Cuánto se muestra de una entidad a lo largo de los 5 actos (Spec-450 §2)."""

    NUNCA = "nunca"
    INSINUADA = "insinuada"
    PROGRESIVA = "progresiva"
    EXPLICITA = "explicita"


MAX_ENTITIES = 3


class Entity(BaseModel):
    """Entidad narrativa: la amenaza de la historia (Spec-450 §1).

    La de `order_index = 0` es la principal: gobierna las reglas de revelación de
    los beats. Los topes de largo cuidan el contexto de los modelos locales.
    """

    id: UUID4 = Field(default_factory=uuid.uuid4)
    story_id: UUID4
    order_index: int
    name: str = Field("", max_length=60)
    nature_id: str = Field(..., min_length=1)
    description: str = Field("", max_length=400)
    manifestations: str = Field("", max_length=300)
    limits: str = Field("", max_length=300)
    reveal_level: RevealLevel = RevealLevel.INSINUADA
    # Etiqueta del catálogo ("Ser del folklore") para los prompts; no se persiste.
    nature_label: str = ""

    @field_validator("name", "nature_id", "description", "manifestations", "limits", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class TypedRule(BaseModel):
    """Regla narrativa con semántica explícita (Spec-043).

    Spec-190 §4.4: `applies_to_beat` define el alcance — `None` = regla global
    (aplica a los 5 actos); `1..N` = regla anclada a ese acto.
    """

    id: str
    story_id: UUID4
    content: str
    applies_to_beat: Optional[int] = None


class Scenario(BaseModel):
    """Escenario cronológico de la historia (Spec 038)."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    story_id: UUID4
    order_index: int
    name: str
    description: str = ""


class ActText(BaseModel):
    """La SALIDA de un acto: su prosa (Spec-570). La entrada es `ActOutline`.

    Los prompts quedan para el debug. Lo que era de la entrada (resumen, sinopsis,
    tipo, escenario) vive en la escaleta.
    """

    number: int
    generated_act: str = ""
    status: BeatStatus = BeatStatus.PENDING
    # Spec-560 A2: se escribió con la memoria de una versión anterior de un acto previo
    # (se regeneró un acto de antes). Se limpia al regenerarlo o al generar todo.
    stale: bool = False
    created_at: datetime = Field(default_factory=now_argentina)
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None

    def is_narrated(self) -> bool:
        """True si el beat tiene prosa generada y está marcado como completado."""
        return bool(self.generated_act and self.status == BeatStatus.COMPLETED)

    def is_pending(self) -> bool:
        """True si el beat aún no fue narrado."""
        return self.status == BeatStatus.PENDING

    def has_content(self) -> bool:
        """True si el beat tiene contenido (independientemente del status)."""
        return bool(self.generated_act)


class NarrativeJournal(BaseModel):
    """Memoria narrativa para coherencia."""

    last_events: str = ""
    physical_emotional_state: str = ""
    # Spec-530 §8.2: imágenes, frases y comparaciones ya usadas (acumuladas por acto).
    used_motifs: list[str] = []
    # Spec-590 E: cómo quedó el cuerpo de quien narra (heridas con el lugar exacto,
    # cansancio, lo que lleva encima), para que el acto siguiente no lo contradiga.
    body_state: str = ""
    # Spec-590 C: gustos, manías, miedos y opiniones que la Voz inventó (acumulados).
    narrator_traits: list[str] = []

    def is_empty(self) -> bool:
        """True si no tiene ningún campo con datos."""
        return not (
            self.last_events
            or self.physical_emotional_state
            or self.used_motifs
            or self.body_state
            or self.narrator_traits
        )


class GeneratedNarrative(BaseModel):
    """Variante narrativa generada a partir de una StoryTemplate."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    story_template_id: UUID4
    title: str
    content: str
    status: StoryStatus = StoryStatus.COMPLETED
    created_at: datetime = Field(default_factory=now_argentina)


# ── Spec-530: asistente de autoría ───────────────────────────────────────────


class CharacterKind(str, Enum):
    """Tipo de personaje (Spec-530 §14): cómo lo nombra la Voz."""

    PERSONA = "persona"  # con nombre propio
    SIN_NOMBRE = "sin_nombre"  # «el sereno», «una señora»
    GRUPO = "grupo"  # «las familias del galpón»


class Direction(BaseModel):
    """Lo que el autor decide al empezar (vista Dirección, Spec-530 §3.2).

    Las decisiones del taller (meta, qué está en juego, historia secreta…) viven
    en `WorkshopItem`, no acá: la dirección es solo lo que el autor escribe.
    """

    premise: str = ""  # «¿De qué trata?»
    effect: str = ""  # pavor | susto | melancolia | revelacion | otro
    effect_other: str = ""  # texto libre cuando effect == "otro"
    ending: str = ""
    # Spec-550 H1: escribir el final es decidirlo. Se deriva de `ending` (el valor que
    # llegue se ignora): con texto, el final es del autor y la IA no lo cambia.
    ending_intentional: bool = False
    telling: str = ""  # «¿Cómo lo cuenta?»: caso | confesion | cronica (Spec-640: sin literario)

    @model_validator(mode="after")
    def _ending_fixed_when_written(self) -> "Direction":
        self.ending_intentional = bool(self.ending.strip())
        return self


class WorkshopLevel(str, Enum):
    """Nivel del taller en el que se evalúa un criterio (Spec-530 §4)."""

    DIRECCION = "direccion"
    ESCALETA = "escaleta"


class CriterionStatus(str, Enum):
    """Semáforo de un criterio del taller."""

    CUMPLE = "cumple"
    PARCIAL = "parcial"
    FALTA = "falta"
    INTENCIONAL = "intencional"


class WorkshopItem(BaseModel):
    """Estado de un criterio del taller: la pregunta vigente y la respuesta.

    Hay una fila por (historia, nivel, criterio); `asked` guarda las preguntas de
    rondas anteriores para filtrar las que «ya no suman» (Spec-530 §3.3).
    """

    level: WorkshopLevel = WorkshopLevel.DIRECCION
    criterion: str = Field(..., min_length=1)
    status: CriterionStatus = CriterionStatus.FALTA
    question: str = ""
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    round: int = Field(1, ge=1)
    question_round: int = Field(0, ge=0)  # ronda en que se hizo la pregunta vigente
    asked: list[str] = Field(default_factory=list)


class OutlineWarning(BaseModel):
    """Un aviso de la revisión de la escaleta (Spec-550 H10).

    `key` identifica el tema del aviso para que un «Ignorar» sobreviva a revisar de
    nuevo: en los de regla es estable («siembra:el ramo», «elenco:el sereno»; un
    aviso que junta varias siembras las une con «|»); en los de la IA, «ia:» + el
    texto normalizado.
    """

    text: str
    key: str = ""
    source: Literal["regla", "ia"] = "ia"
    dismissed: bool = False

    def keys(self) -> set[str]:
        return {k for k in self.key.split("|") if k}

    @classmethod
    def from_ai(cls, text: str) -> "OutlineWarning":
        text = " ".join(text.split())
        return cls(text=text, key=f"ia:{normalize_key(text)}", source="ia")


def normalize_key(text: str) -> str:
    """Minúsculas, sin tildes ni signos, espacios simples: «¿El ramo?» → «el ramo»."""
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w\s]", " ", plain).split())


class ActOutline(BaseModel):
    """Un acto de la escaleta (Spec-530 §3.2): lo edita el usuario y lo propone la IA.

    Es la entrada del acto, separada de `ActText` (que es la salida generada).
    `on_stage` y `scenario` van por nombre: personajes y escenarios se reescriben
    con ids nuevos al editar la historia.
    """

    number: int = Field(..., ge=1, le=5)
    # Spec-560 A1: «Cómo llega acá» (actos 2–5): cuánto tiempo pasó y qué pasó entre el
    # final del acto anterior y el primer hecho de este. La Voz abre el acto con esto.
    bridge: str = ""
    goal: str = ""
    events: list[str] = Field(default_factory=list)
    change_from: str = ""
    change_to: str = ""
    scenario: str = ""
    on_stage: list[str] = Field(default_factory=list)
    held_back: str = ""  # «lo que todavía no se cuenta» (Spec-560 A4)
    reveal_act: int = Field(0, ge=0, le=5)  # en qué acto se revela; 0 = sin definir
    seeds: list[str] = Field(default_factory=list)
    payoffs: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    warnings: list[OutlineWarning] = Field(default_factory=list)
    needs_review: bool = False
    # Spec-570 D2: acto importado de un YAML viejo (solo su sinopsis). Una escaleta de
    # borradores se planifica igual que una vacía; el Planificador los usa de guía.
    draft: bool = False
    # Lo que el autor escribió para este acto en un YAML viejo: guía del Planificador y
    # vuelve al exportar (Spec-440 §8). Sobrevive a que el Planificador arme el acto.
    synopsis: str = ""

    @field_validator("warnings", mode="before")
    @classmethod
    def _plain_texts(cls, value):
        # Un texto suelto es un aviso de la IA (también lo que guardaba la Spec-530).
        return [OutlineWarning.from_ai(w) if isinstance(w, str) else w for w in value or []]

    def visible_warnings(self) -> list[OutlineWarning]:
        return [w for w in self.warnings if not w.dismissed]

    def dismissed_keys(self) -> set[str]:
        return {k for w in self.warnings if w.dismissed for k in w.keys()}


StructureId = Literal["largo", "corto"]  # Spec-650: largo = 5 actos, corto = 3


class Story(BaseModel):
    """Historia base."""

    id: UUID4 = Field(default_factory=uuid.uuid4)
    title: str = Field(..., min_length=1)
    protagonista: str = Field(..., min_length=1)
    relator: str = Field(..., min_length=1)
    sinopsis: str = Field(..., min_length=1)
    genero: str = ""
    subgenero: str = ""
    reglas: list[str] = []
    beats: list[ActText] = []
    scenarios: list[Scenario] = []
    entities: list[Entity] = []
    journal: NarrativeJournal = Field(default_factory=NarrativeJournal)
    status: StoryStatus = StoryStatus.DRAFT
    created_at: datetime = Field(default_factory=now_argentina)

    narrator_config: Optional[dict] = None
    typed_rules: list[TypedRule] = []
    personajes_full: list[dict] = []

    # Spec-650: estructura del relato (id de `estructuras` en llm_beats_definition.yaml;
    # un test verifica que estos valores y los del YAML son los mismos).
    structure: StructureId = "largo"

    # Spec-530: asistente de autoría (vacíos en las historias del wizard).
    direction: Optional[Direction] = None
    workshop: list[WorkshopItem] = []
    outline: list[ActOutline] = []

    @field_validator("title", "protagonista", "relator", "sinopsis", mode="before")
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @property
    def atmosfera(self) -> str:
        """`genero (subgenero)`: el tipo de horror en un solo string (Spec-530 S7)."""
        subgenero = f" ({self.subgenero})" if self.subgenero else ""
        return f"{self.genero or ''}{subgenero}".strip()

    @property
    def principal_entity(self) -> Optional[Entity]:
        """La entidad principal (la primera) o `None` si no hay (Spec-450)."""
        return self.entities[0] if self.entities else None

    # -- Spec 070: comportamiento de dominio --

    def has_beats(self) -> bool:
        """True si la historia tiene al menos un beat."""
        return bool(self.beats)

    def beat_count(self) -> int:
        """Número de beats de la historia."""
        return len(self.beats)

    def get_pending_beats(self) -> list[ActText]:
        """Retorna los beats que aún no fueron narrados."""
        return [b for b in self.beats if b.is_pending()]

    def get_completed_beats(self) -> list[ActText]:
        """Retorna los beats completamente narrados."""
        return [b for b in self.beats if b.is_narrated()]

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

    def get_beat_by_number(self, n: int) -> ActText | None:
        """Retorna el beat con ese número, o None si no existe."""
        return next((b for b in self.beats if b.number == n), None)

    def get_first_beat(self) -> ActText | None:
        """Retorna el primer beat (menor número), o None si no hay beats."""
        return min(self.beats, key=lambda b: b.number) if self.beats else None

    def get_last_beat(self) -> ActText | None:
        """Retorna el último beat (mayor número), o None si no hay beats."""
        return max(self.beats, key=lambda b: b.number) if self.beats else None
