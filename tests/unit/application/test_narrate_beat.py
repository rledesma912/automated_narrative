"""VozUseCase.narrate_with_prompts (Spec-530 S7): prosa limpia de un acto."""

import re

import pytest

from src.application.use_cases import VozUseCase
from src.domain.exceptions import LLMResponseError
from src.domain.interfaces import LLMResponse
from src.domain.models import BeatStatus, MacroBeat
from src.infrastructure.adapters import MockLLMAdapter


def _beat() -> MacroBeat:
    return MacroBeat(number=1, summary="- Hecho", status="pending")


async def test_guarda_prosa_y_prompts_en_el_acto():
    use_case = VozUseCase(MockLLMAdapter(fixed_response="El viejo molino crujía."))

    beat, _ = await use_case.narrate_with_prompts(_beat(), "SISTEMA", "USUARIO")

    assert beat.generated_act == "El viejo molino crujía."
    assert (beat.system_prompt, beat.user_prompt) == ("SISTEMA", "USUARIO")
    assert beat.status == BeatStatus.COMPLETED


async def test_usa_el_normalizer_inyectado():
    class StripHeadings:
        def normalize(self, text: str, model_name: str = "") -> str:
            return re.sub(r"^##.*\n\n", "", text)

    llm = MockLLMAdapter(fixed_response="## Título indeseado\n\nTexto del relato.")
    beat, _ = await VozUseCase(llm, normalizer=StripHeadings()).narrate_with_prompts(
        _beat(), "s", "p"
    )
    assert beat.generated_act == "Texto del relato."


async def test_respuesta_vacia_es_error():
    with pytest.raises(LLMResponseError):
        await VozUseCase(MockLLMAdapter(fixed_response="")).narrate_with_prompts(_beat(), "s", "p")


async def test_una_negativa_se_reintenta():
    responses = ["Lo siento, no puedo escribir eso.", "El viejo molino crujía."]
    calls = 0

    class Sequential:
        async def generate(self, prompt, **_kw):
            nonlocal calls
            text = responses[min(calls, len(responses) - 1)]
            calls += 1
            return LLMResponse(text=text, context=None)

    beat, _ = await VozUseCase(Sequential()).narrate_with_prompts(_beat(), "s", "p")
    assert calls >= 2 and "molino" in beat.generated_act
