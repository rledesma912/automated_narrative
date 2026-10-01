"""Spec-610 T2.3/T2.5: armar el paquete con el mock, reintentar y fallar con un mensaje claro."""

import json
import uuid

import pytest

from src.application.services.video.service import VideoScriptError, VideoScriptService
from src.domain.interfaces import LLMResponse
from src.domain.models import GeneratedNarrative, Story
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.adapters.mock_structured import mock_structured

CONTENT = "\n\n".join(
    f"## Acto {a}\n\n" + "\n\n".join(f"Párrafo {p} del acto {a}." for p in range(1, 4))
    for a in range(1, 6)
)


def _story() -> Story:
    return Story(
        title="No te detengas en el bosque",
        protagonista="Ernesto",
        relator="Primera persona",
        sinopsis="Un camión se queda en el bosque.",
    )


def _narrative(story: Story, content: str = CONTENT) -> GeneratedNarrative:
    return GeneratedNarrative(story_template_id=story.id, title="v1", content=content)


class _ScriptedLLM:
    """Devuelve las respuestas en orden; la última se repite. Guarda los prompts."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if answer == "mock":
            answer = mock_structured("guion", {}, prompt)
        return LLMResponse(text=json.dumps(answer))


async def test_con_el_mock_sale_un_paquete_valido():
    story = _story()
    narrative = _narrative(story)

    script = await VideoScriptService(MockLLMAdapter()).generate(story, narrative)

    assert script.narrative_id == narrative.id
    assert len(script.bloques) == 15
    assert 10 <= len(script.momentos) <= 15
    assert script.parrafos_por_acto == {n: 3 for n in range(1, 6)}
    assert script.lector == "Lucas"
    assert script.calabaza.outro.endswith("Buenas noches.")


async def test_reintenta_una_vez_con_los_problemas():
    story = _story()
    malo = mock_structured("guion", {}, "")  # sin actos: no cubre nada
    llm = _ScriptedLLM(malo, "mock")

    script = await VideoScriptService(llm).generate(story, _narrative(story))

    assert len(llm.prompts) == 2
    assert "LA RESPUESTA ANTERIOR TENÍA ESTOS PROBLEMAS" in llm.prompts[1]
    assert "faltan los párrafos 1, 2, 3" in llm.prompts[1]
    assert script.bloques


async def test_si_falla_dos_veces_el_mensaje_es_claro():
    story = _story()
    llm = _ScriptedLLM(mock_structured("guion", {}, ""))

    with pytest.raises(VideoScriptError, match="La IA no pudo armar un guion que cumpla todo"):
        await VideoScriptService(llm).generate(story, _narrative(story))
    assert len(llm.prompts) == 2


async def test_un_relato_sin_actos():
    story = _story()
    with pytest.raises(VideoScriptError, match="no está separado en actos"):
        await VideoScriptService(MockLLMAdapter()).generate(story, _narrative(story, "Texto."))


def test_ids_distintos_semillas_distintas():
    from src.application.services.video.type_mix import seed_for

    assert seed_for(uuid.uuid4()) != seed_for(uuid.uuid4())
