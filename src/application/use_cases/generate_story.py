from uuid import UUID
from typing import Optional
from src.domain.models import Story, GeneratedAct, NarrativeState, StoryStatus
from src.domain.interfaces import LLMProvider, StoryRepository, StateExtractor
from src.application.services.prompt_builder import PromptBuilder
from src.infrastructure.normalizers.response_normalizer import LLMResponseNormalizer

class GenerateStoryUseCase:
    """Orquestador (Pipeline) de generación de historias acto por acto."""
    
    def __init__(
        self, 
        llm: LLMProvider, 
        repository: StoryRepository,
        normalizer: LLMResponseNormalizer,
        state_extractor: Optional[StateExtractor] = None
    ):
        self.llm = llm
        self.repository = repository
        self.normalizer = normalizer
        self.state_extractor = state_extractor
        self.prompt_builder = PromptBuilder()

    async def generate_act(self, story_id: UUID, act_number: int) -> GeneratedAct:
        """Genera un acto específico de la historia."""
        
        # 1. Obtener la historia de la DB
        story = await self.repository.get_story(story_id)
        if not story:
            raise ValueError(f"Historia {story_id} no encontrada.")
        
        # 2. Obtener el acto_input correspondiente
        act_input = next((a for a in story.actos_input if a.number == act_number), None)
        if not act_input:
            raise ValueError(f"Acto {act_number} no definido en la historia.")
            
        # 3. Obtener el estado narrativo previo (si no es el acto 1)
        previous_state = None
        if act_number > 1:
            acts = await self.repository.get_acts(story_id)
            prev_act = next((a for a in acts if a.number == act_number - 1), None)
            if prev_act:
                previous_state = prev_act.state_after
        
        # 4. Construir Prompts
        system_prompt = self.prompt_builder.build_system_prompt(story)
        act_prompt = self.prompt_builder.build_act_prompt(story, act_input, previous_state)
        
        # 5. Llamada al LLM (Implementación del Adaptador)
        raw_output = await self.llm.generate(
            prompt=act_prompt, 
            system_prompt=system_prompt,
            model="qwen2.5:32b"  # Por defecto del Spec
        )
        
        # 6. Normalización (Limpieza de <think>, markdown, etc.)
        clean_content = self.normalizer.normalize(raw_output)
        
        # 7. Extracción de Estado (Preparado para Hito 2)
        new_state = None
        if self.state_extractor:
            new_state = await self.state_extractor.extract_state(clean_content, previous_state)
        else:
            # Fallback a estado vacío si aún no implementamos el extractor
            new_state = NarrativeState()
            
        # 8. Crear y Guardar el Acto Generado
        generated_act = GeneratedAct(
            number=act_number,
            content=clean_content,
            raw_output=raw_output,
            word_count=len(clean_content.split()),
            state_after=new_state
        )
        
        await self.repository.save_act(story_id, generated_act)
        
        return generated_act
