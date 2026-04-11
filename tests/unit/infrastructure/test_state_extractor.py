import pytest
from unittest.mock import AsyncMock
from src.infrastructure.adapters.state_extractor import OllamaStateExtractor
from src.domain.models import NarrativeState

@pytest.mark.asyncio
async def test_state_extraction_success():
    """Valida que el extractor convierta el JSON del LLM en un objeto NarrativeState."""
    # 1. Mock de LLM que devuelve un JSON "sucio" (con texto extra)
    llm_response = """
Aquí tienes el JSON:
{
  "location": "El Sótano",
  "characters": "Marcos (herido)",
  "situation": "Encerrado",
  "active_threat": "Sombra",
  "goal": "Encontrar la llave",
  "last_action": "Gritar"
}
"""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = llm_response
    
    extractor = OllamaStateExtractor(llm=mock_llm)
    
    # 2. Ejecutar
    state = await extractor.extract_state("Contenido del relato...")
    
    # 3. Validar
    assert isinstance(state, NarrativeState)
    assert state.location == "El Sótano"
    assert state.characters == "Marcos (herido)"
    assert state.active_threat == "Sombra"

@pytest.mark.asyncio
async def test_state_extraction_fallback():
    """Valida que si el LLM devuelve basura, el extractor use el fallback (estado anterior o vacío)."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "No pude encontrar el estado, lo siento."
    
    previous = NarrativeState(location="Bosque")
    extractor = OllamaStateExtractor(llm=mock_llm)
    
    # Ejecutar con estado previo
    state = await extractor.extract_state("...", previous_state=previous)
    
    # Debe devolver el anterior para no perder la continuidad
    assert state.location == "Bosque"
