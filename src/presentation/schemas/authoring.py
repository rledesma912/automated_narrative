"""Esquemas de la API del asistente de autoría (Spec-530 S3)."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.application.services.authoring.catalog import topes
from src.domain.models import StructureId

# Spec-760: los topes salen de `config/authoring_options.yaml` (los mismos que ve la pantalla).
_T = topes()


def _texto(campo: str):
    """Un texto de una lista (un hecho, una regla) con su tope."""
    return Annotated[str, Field(max_length=_T[campo])]


class ThreatForm(BaseModel):
    """La amenaza (opcional): la entidad principal de la Spec-450."""

    name: str = Field("", max_length=_T["threat_name"])
    nature: str = ""
    description: str = Field("", max_length=_T["threat_description"])
    manifestations: str = Field("", max_length=_T["threat_manifestations"])
    limits: str = Field("", max_length=_T["threat_limits"])
    reveal_level: str = "insinuada"


class DirectionForm(BaseModel):
    """La vista Dirección completa. El frontend la manda entera en cada guardado."""

    title: str = Field(..., min_length=1, max_length=_T["title"])
    genero: str = ""
    subgenero: str = ""
    premise: str = Field("", max_length=_T["premise"])  # «¿De qué trata?» (Spec-760)
    effect: str = ""
    effect_other: str = Field("", max_length=_T["effect_other"])
    ending: str = Field("", max_length=_T["ending"])
    ending_intentional: bool = False
    telling: str = ""
    # Spec-670: la clase de historia y, con «Otra», cómo la cuenta el autor (Spec-780: sin giro).
    form: str = ""
    form_other: str = Field("", max_length=_T["form_other"])
    habla: str = ""  # Spec-680 C1: cómo habla quien narra ("" = la de siempre)
    protagonist_name: str = Field("", max_length=_T["protagonist_name"])
    protagonist_role: str = Field("", max_length=_T["protagonist_role"])
    narrator: str = Field("", max_length=_T["narrator"])  # "" = el protagonista
    threat: ThreatForm | None = None  # sin naturaleza = sin amenaza
    # Spec-650 D9: solo al crear (POST). El autoguardado (PUT) la ignora: el largo se
    # cambia únicamente con PUT …/structure, que confirma y rearma.
    structure: StructureId = "medio"


class StructureForm(BaseModel):
    """Spec-650: cambiar el largo de la historia (borra los actos y reubica las reglas)."""

    structure: StructureId


class WorkshopAction(BaseModel):
    """Lo que hace el autor con un criterio del taller."""

    action: Literal["answer", "decide", "intentional", "reopen", "keep"]  # keep: Spec-700 D18
    # Spec-760: el tope más grande (el del final, que sale de la idea); el de una respuesta
    # común lo controla el router, que sabe de qué criterio es.
    text: str = Field("", max_length=max(_T["answer"], _T["final"]))


class ActForm(BaseModel):
    """Un acto de la escaleta editado por el autor."""

    bridge: str = Field("", max_length=_T["bridge"])  # «Cómo llega acá» (Spec-560 A1)
    goal: str = Field("", max_length=_T["goal"])
    events: list[_texto("event")] = Field(default_factory=list, max_length=_T["events"])
    # Spec-710 D1: el lugar de cada hecho, en el mismo orden ("" = el del anterior). Sin la
    # lista (una pestaña vieja), se conserva la guardada si los hechos no cambiaron de largo.
    event_places: list[str] | None = Field(None, max_length=_T["events"])
    change_from: str = Field("", max_length=_T["change_from"])
    change_to: str = Field("", max_length=_T["change_to"])
    scenario: str = Field("", max_length=_T["scenario"])
    on_stage: list[str] = Field(default_factory=list, max_length=_T["on_stage"])
    held_back: str = Field("", max_length=_T["held_back"])
    reveal_act: int = Field(0, ge=0, le=5)  # en qué acto se revela (Spec-560 A4)
    seeds: list[str] = Field(default_factory=list)
    payoffs: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    rules: list[_texto("rule")] = Field(
        default_factory=list, max_length=_T["rules"]
    )  # reglas de este acto


class CharacterForm(BaseModel):
    """Un personaje que aparece en un acto (Spec-530 §14: se suma cuando hace falta)."""

    name: str = Field(..., min_length=1, max_length=_T["character_name"])
    kind: Literal["persona", "sin_nombre", "grupo"] = "sin_nombre"
    relation: str = Field("", max_length=_T["character_relation"])
    act: int | None = Field(None, ge=1, le=5)  # Spec-630 B2: queda en «Quiénes están» de ese acto


class ScenarioForm(BaseModel):
    """Spec-630 B6: un lugar nuevo para la historia (y, si viene `act`, elegido en ese acto)."""

    name: str = Field(..., min_length=1, max_length=_T["scenario"])
    act: int | None = Field(None, ge=1, le=5)
    event: int | None = Field(None, ge=0)  # Spec-710 D13: con `act`, el lugar de ese hecho


class NameForm(BaseModel):
    """Spec-630 B7: qué lugar o personaje se borra (por nombre: los actos los guardan así)."""

    name: str = Field(..., min_length=1, max_length=120)


class IdeaRevisadaForm(BaseModel):
    """Spec-700 D16: en qué paso se deja la idea como está; D27: `respuestas` = la autora
    ya revisó lo que cambió y la IA no pudo revisar."""

    paso: Literal["preguntas", "actos", "respuestas", "local"]  # local: Spec-720 D7


class SameCharacterForm(BaseModel):
    """Spec-700 B4: «Amigos de Ximena» es «Amigas de Ximena», que ya está en la lista."""

    name: str = Field(..., min_length=1, max_length=120)
    same_as: str = Field(..., min_length=1, max_length=120)


class WarningDismiss(BaseModel):
    """Spec-550 H10: el aviso se identifica por su clave (tema), no por el texto."""

    key: str = Field(..., min_length=1)
