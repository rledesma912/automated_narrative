import pytest
import os
from uuid import uuid4
from unittest.mock import AsyncMock
from src.application.use_cases.export_story import ExportStoryUseCase
from src.infrastructure.renderers.markdown_renderer import MarkdownRenderer
from src.domain.models import Story, GeneratedAct

@pytest.mark.asyncio
async def test_export_story_generates_file():
    """Valida que el caso de uso de exportación cree un archivo físico."""
    # 1. Preparar datos
    story_id = uuid4()
    mock_story = Story(
        id=story_id,
        title="Relato de Prueba",
        protagonistas="Marcos",
        relator="Narrador",
        escenarios="Casa",
        sinopsis="...",
        atmosfera="Terror"
    )
    
    mock_acts = [
        GeneratedAct(number=1, content="Era una noche oscura.", raw_output="", word_count=4),
        GeneratedAct(number=2, content="Algo se movió.", raw_output="", word_count=3)
    ]
    
    repo = AsyncMock()
    repo.get_story.return_value = mock_story
    repo.get_acts.return_value = mock_acts
    
    renderer = MarkdownRenderer() # Usa las plantillas reales
    use_case = ExportStoryUseCase(repository=repo, renderer=renderer)
    
    # 2. Ejecutar
    file_path = await use_case.execute(story_id)
    
    # 3. Validar
    assert os.path.exists(file_path)
    assert "Relato_de_Prueba" in file_path
    
    # Leer contenido para validar Jinja2
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# Relato de Prueba" in content
        assert "Acto 1" in content
        assert "Era una noche oscura." in content
        
    # Limpieza
    if os.path.exists(file_path):
        os.remove(file_path)
