import pytest
from uuid import UUID
from datetime import datetime
from src.domain.models import Story, ActInput, StoryStatus, NarrativeState

def test_create_story_success():
    """Valida que una historia se cree con los datos mínimos y genere sus defaults."""
    story_data = {
        "title": "El Monte Prohibido",
        "protagonistas": "Marcos y Sofía",
        "relator": "Marcos (1ra persona)",
        "escenarios": "Bosque oscuro",
        "sinopsis": "Dos hermanos se pierden en un bosque maldito.",
        "atmosfera": "Horror opresivo",
        "reglas": ["No mirar atrás", "No hablar con extraños"],
        "actos_input": [
            {"number": 1, "title": "La llegada", "mission": "Llegar al claro del bosque"}
        ]
    }
    
    story = Story(**story_data)
    
    assert isinstance(story.id, UUID)
    assert story.title == "El Monte Prohibido"
    assert story.status == StoryStatus.PENDING
    assert isinstance(story.created_at, datetime)
    assert len(story.reglas) == 2
    assert len(story.actos_input) == 1
    assert story.actos_input[0].title == "La llegada"

def test_narrative_state_defaults():
    """Valida que el estado narrativo inicie vacío y limpio."""
    state = NarrativeState()
    assert state.location == ""
    assert state.characters == ""
    assert state.situation == ""
    assert state.active_threat == ""
    assert state.goal == ""
    assert state.last_action == ""

def test_story_invalid_status():
    """Valida que Pydantic rechace estados no definidos en el Enum."""
    from pydantic import ValidationError
    
    with pytest.raises(ValidationError):
        Story(
            title="Test",
            protagonistas="...",
            relator="...",
            escenarios="...",
            sinopsis="...",
            atmosfera="...",
            status="estado_inventado"
        )
