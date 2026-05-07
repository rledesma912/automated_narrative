"""Story DTOs."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StoryCreateDTO(BaseModel):
    """DTO for creating a story."""

    title: str = Field(..., min_length=1)
    protagonista: str = Field(..., min_length=1)
    relator: str = Field(..., min_length=1)
    escenarios: list[str] = []
    sinopsis: str = Field(..., min_length=1)
    atmosfera: str = Field(..., min_length=1)
    reglas: list[str] = []
    storyteller_config: Optional[dict] = None
    typed_rules: list[dict] = []
    personajes_full: list[dict] = []

    @field_validator("title", "protagonista", "relator", "sinopsis", "atmosfera", mode="before")
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v
