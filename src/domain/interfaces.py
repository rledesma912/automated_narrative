from typing import Protocol, List, Optional
from uuid import UUID
from .models import Story, GeneratedAct, NarrativeState

class LLMProvider(Protocol):
    """Interfaz para comunicación con modelos de lenguaje (Ollama, OpenAI, Mock)."""
    async def generate(self, prompt: str, temperature: float = 0.7) -> str:
        ...

class StoryRepository(Protocol):
    """Interfaz para la persistencia de historias y actos."""
    async def save_story(self, story: Story) -> None:
        ...
    
    async def get_story(self, story_id: UUID) -> Optional[Story]:
        ...
    
    async def save_act(self, story_id: UUID, act: GeneratedAct) -> None:
        ...
    
    async def get_acts(self, story_id: UUID) -> List[GeneratedAct]:
        ...
    
    async def update_status(self, story_id: UUID, status: str) -> None:
        ...

class StateExtractor(Protocol):
    """Interfaz para la extracción de estado narrativo."""
    async def extract_state(self, act_content: str, previous_state: Optional[NarrativeState] = None) -> NarrativeState:
        ...
