"""Story DTOs."""

from typing import Optional

from pydantic import BaseModel


class StoryCreateDTO(BaseModel):
    """DTO for creating a story."""

    title: str
    protagonista: str
    relator: str
    escenarios: list[str] = []
    sinopsis: str
    atmosfera: str
    reglas: list[str] = []
    storyteller_config: Optional[dict] = None
    typed_rules: list[dict] = []
    personajes_full: list[dict] = []
