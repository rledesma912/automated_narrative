"""Esquemas de la API del asistente de autoría (Spec-530 S3)."""

from typing import Literal

from pydantic import BaseModel, Field


class DirectionForm(BaseModel):
    """La vista Dirección completa. El frontend la manda entera en cada guardado."""

    title: str = Field(..., min_length=1, max_length=120)
    genero: str = ""
    subgenero: str = ""
    premise: str = Field("", max_length=2000)  # «¿De qué trata?»
    effect: str = ""
    effect_other: str = Field("", max_length=200)
    ending: str = Field("", max_length=600)
    ending_intentional: bool = False
    telling: str = ""
    protagonist_name: str = Field("", max_length=60)
    protagonist_role: str = Field("", max_length=160)
    narrator: str = Field("", max_length=60)  # "" = el protagonista


class WorkshopAction(BaseModel):
    """Lo que hace el autor con un criterio del taller."""

    action: Literal["answer", "decide", "intentional", "reopen"]
    text: str = Field("", max_length=600)


class ActForm(BaseModel):
    """Un acto de la escaleta editado por el autor."""

    goal: str = Field("", max_length=300)
    events: list[str] = Field(default_factory=list, max_length=8)
    change_from: str = Field("", max_length=200)
    change_to: str = Field("", max_length=200)
    scenario: str = Field("", max_length=120)
    on_stage: list[str] = Field(default_factory=list, max_length=12)
    held_back: str = Field("", max_length=300)
    seeds: list[str] = Field(default_factory=list)
    payoffs: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
