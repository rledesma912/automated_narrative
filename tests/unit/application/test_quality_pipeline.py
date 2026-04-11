import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from src.application.use_cases.generate_story import GenerateStoryUseCase
from src.domain.models import Story, ActInput, NarrativeState
from src.domain.exceptions import QualityValidationError
from src.infrastructure.normalizers.response_normalizer import LLMResponseNormalizer
from src.application.services.quality_validator import QualityValidator

@pytest.fixture
def mock_story():
    return Story(
        id=uuid4(),
        title="Pipeline Test Story",
        protagonistas="...",
        relator="...",
        escenarios="...",
        sinopsis="...",
        atmosfera="Horror",
        actos_input=[ActInput(number=1, title="Intro", mission="...")]
    )

@pytest.mark.asyncio
async def test_full_pipeline_success(mock_story):
    """Valida el flujo exitoso: Normalizar -> Validar -> Extraer Estado."""
    # 1. Mocks
    repo = AsyncMock()
    repo.get_story.return_value = mock_story
    repo.save_act = AsyncMock()
    
    # Respuesta con <think> y longitud suficiente
    raw_response = "<think>Analizando...</think> " + ("Había una vez un bosque oscuro. " * 30)
    llm = AsyncMock()
    llm.generate.return_value = raw_response
    
    # Extractor Mock
    new_state = NarrativeState(location="El Claro")
    extractor = AsyncMock()
    extractor.extract_state.return_value = new_state
    
    # 2. Instanciar Pipeline
    use_case = GenerateStoryUseCase(
        llm=llm,
        repository=repo,
        normalizer=LLMResponseNormalizer(),
        state_extractor=extractor,
        validator=QualityValidator(min_words=20) # Reducido para el test
    )
    
    # 3. Ejecutar
    act = await use_case.generate_act(mock_story.id, 1)
    
    # 4. Validar
    assert "think" not in act.content
    assert act.state_after.location == "El Claro"
    assert act.word_count >= 20
    assert repo.save_act.called

@pytest.mark.asyncio
async def test_pipeline_fails_quality(mock_story):
    """Valida que el pipeline lance error si el relato es demasiado corto."""
    repo = AsyncMock()
    repo.get_story.return_value = mock_story
    
    # Respuesta corta
    llm = AsyncMock()
    llm.generate.return_value = "Muy corto."
    
    use_case = GenerateStoryUseCase(
        llm=llm,
        repository=repo,
        normalizer=LLMResponseNormalizer(),
        validator=QualityValidator(min_words=50) # Esperamos 50, recibimos 2
    )
    
    # 3. Ejecutar y validar excepción
    with pytest.raises(QualityValidationError) as exc:
        await use_case.generate_act(mock_story.id, 1)
    
    assert "demasiado corto" in str(exc.value)

@pytest.mark.asyncio
async def test_pipeline_fails_technical_residue(mock_story):
    """Valida que el pipeline lance error si quedan residuos técnicos (ej: JSON)."""
    repo = AsyncMock()
    repo.get_story.return_value = mock_story
    
    # Respuesta con JSON residual que el normalizador no pudo limpiar
    raw_response = "El relato fue generado correctamente. { \"json\": \"error\" }"
    llm = AsyncMock()
    llm.generate.return_value = raw_response
    
    use_case = GenerateStoryUseCase(
        llm=llm,
        repository=repo,
        normalizer=LLMResponseNormalizer(),
        validator=QualityValidator(min_words=5) 
    )
    
    # 3. Ejecutar y validar excepción de residuos
    with pytest.raises(QualityValidationError) as exc:
        await use_case.generate_act(mock_story.id, 1)
    
    assert "residuos técnicos" in str(exc.value)
