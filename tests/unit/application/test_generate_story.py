import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from src.application.use_cases.generate_story import GenerateStoryUseCase
from src.domain.models import Story, ActInput, GeneratedAct
from src.infrastructure.adapters.mock_adapter import MockLLMAdapter
from src.infrastructure.normalizers.response_normalizer import LLMResponseNormalizer

@pytest.mark.asyncio
async def test_generate_act_orchestration():
    """Valida que el orquestador llame a todos los componentes en orden."""
    # 1. Preparar Mocks
    story_id = uuid4()
    mock_story = Story(
        id=story_id,
        title="Test Story",
        protagonistas="...",
        relator="...",
        escenarios="...",
        sinopsis="...",
        atmosfera="Horror",
        actos_input=[ActInput(number=1, title="Acto 1", mission="Misión 1")]
    )
    
    # Mock de repositorio
    repo = AsyncMock()
    repo.get_story.return_value = mock_story
    repo.save_act = AsyncMock()
    
    # Mock de LLM con respuesta "sucia"
    raw_response = "<think>Pensamiento...</think>Relato puro."
    llm = MockLLMAdapter(response_to_return=raw_response)
    
    # Normalizador real
    normalizer = LLMResponseNormalizer()
    
    # 2. Instanciar Caso de Uso
    use_case = GenerateStoryUseCase(
        llm=llm,
        repository=repo,
        normalizer=normalizer
    )
    
    # 3. Ejecutar
    generated_act = await use_case.generate_act(story_id, 1)
    
    # 4. Validar
    assert generated_act.number == 1
    assert generated_act.content == "Relato puro."  # Validamos que se normalizó
    assert generated_act.raw_output == raw_response
    
    # Verificar que el repositorio fue llamado para guardar
    repo.save_act.assert_called_once()
    assert repo.get_story.called
