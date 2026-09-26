import pytest
from pydantic import BaseModel

from src.application.services.authoring.structured_llm import generate_structured
from src.domain.exceptions import LLMStructuredOutputError
from tests.unit.application.authoring.conftest import ScriptedLLM


class Salida(BaseModel):
    x: int


async def _run(llm):
    return await generate_structured(
        llm, role="consultor", prompt="p", system_prompt="s", output=Salida
    )


async def test_valida_y_manda_el_esquema():
    llm = ScriptedLLM({"x": 3})
    result, elapsed = await _run(llm)
    assert result.x == 3 and elapsed == 1.0
    assert llm.calls[0]["response_schema"] == Salida.model_json_schema()
    assert llm.calls[0]["role"] == "consultor"


async def test_quita_el_cerco_de_markdown():
    result, _ = await _run(ScriptedLLM('```json\n{"x": 1}\n```'))
    assert result.x == 1


async def test_reintenta_una_vez():
    llm = ScriptedLLM("no es json", {"x": 2})
    result, elapsed = await _run(llm)
    assert result.x == 2 and len(llm.calls) == 2 and elapsed == 2.0


async def test_dos_fallos_lanzan_error_claro():
    with pytest.raises(LLMStructuredOutputError, match="consultor.*x"):
        await _run(ScriptedLLM({"y": 1}, {"x": "no"}))
