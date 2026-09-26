"""LLM guionado para los servicios del asistente (Spec-530)."""

import json

import pytest

from src.domain.interfaces import LLMResponse
from src.domain.models import Direction, Story


class ScriptedLLM:
    """Devuelve las respuestas en orden y registra cada llamada."""

    def __init__(self, *responses):
        self.responses = [r if isinstance(r, str) else json.dumps(r) for r in responses]
        self.calls: list[dict] = []

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        self.calls.append({"prompt": prompt, **kwargs})
        return LLMResponse(text=self.responses.pop(0), elapsed_s=1.0)

    async def close(self) -> None:
        pass


@pytest.fixture
def story() -> Story:
    return Story(
        title="la pena del colectivo",
        protagonista="José: chofer de micros",
        relator="Primera persona. Narrador: José.",
        sinopsis="José ve por el espejo a una mujer que murió en su micro.",
        narrator_config={"storyteller_name": "José"},
        personajes_full=[{"name": "José", "role": "Chofer"}],
        direction=Direction(
            premise="José ve por el espejo a una mujer que murió en su micro.",
            effect="pavor",
            ending="Descansa en paz.",
            ending_intentional=True,
            telling="caso",
        ),
    )
