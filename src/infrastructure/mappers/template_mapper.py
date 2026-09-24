"""TemplateMapper - adapta input del template al modelo del dominio."""

import uuid
from dataclasses import dataclass

from src.domain.models import Scenario, Story


@dataclass
class TemplateInput:
    """Input del template (español)."""

    title: str
    protagonista: str
    relator: str
    genero: str = ""
    subgenero: str = ""
    tono: str = ""
    atmosfera: str = ""
    escenarios: str = ""
    sinopsis: str = ""
    reglas: list[str] | None = None


class TemplateMapper:
    """Adapter: traduce input español → modelo dominio inglés."""

    def __init__(self):
        self._relator_mapping = {
            "tercera_persona": "third_person",
            "primera_persona": "first_person",
        }

    def map(self, input_data: TemplateInput) -> Story:
        """Traduce input del template al modelo Story."""
        story_id = uuid.uuid4()
        scenarios = []
        if input_data.escenarios:
            for i, name in enumerate(
                s.strip() for s in input_data.escenarios.split("/") if s.strip()
            ):
                scenarios.append(Scenario(story_id=story_id, order_index=i, name=name))

        genero, subgenero, tono = self._parse_atmosfera(input_data)

        return Story(
            id=story_id,
            title=input_data.title,
            protagonista=input_data.protagonista,
            relator=self._map_relator(input_data.relator),
            sinopsis=input_data.sinopsis,
            genero=genero,
            subgenero=subgenero,
            tono=tono,
            reglas=input_data.reglas or [],
            scenarios=scenarios,
        )

    def _parse_atmosfera(self, input_data: TemplateInput) -> tuple[str, str, str]:
        """Parsea atmosfera legacy o usa los nuevos campos."""
        if input_data.genero:
            return input_data.genero, input_data.subgenero, input_data.tono
        if input_data.atmosfera:
            parts = input_data.atmosfera.split(" - ")
            genero = parts[0] if parts else ""
            subgenero = ""
            tono = parts[1] if len(parts) > 1 else ""
            return genero, subgenero, tono
        return "", "", ""

    def _map_relator(self, relator: str) -> str:
        """Mapea relator español a inglés."""
        return self._relator_mapping.get(relator, relator)
