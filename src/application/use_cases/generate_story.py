from typing import Optional
from uuid import UUID

from src.application.services.prompt_builder import PromptBuilder
from src.application.services.quality_validator import QualityValidator
from src.domain.interfaces import LLMProvider, StateExtractor, StoryRepository
from src.domain.models import GeneratedAct, NarrativeState
from src.infrastructure.normalizers.response_normalizer import LLMResponseNormalizer


class GenerateStoryUseCase:
    """Orquestador (Pipeline) de generación de historias acto por acto."""
    
    def __init__(
        self, 
        llm: LLMProvider, 
        repository: StoryRepository,
        normalizer: LLMResponseNormalizer,
        state_extractor: Optional[StateExtractor] = None,
        validator: Optional[QualityValidator] = None
    ):
        self.llm = llm
        self.repository = repository
        self.normalizer = normalizer
        self.state_extractor = state_extractor
        self.validator = validator or QualityValidator(min_words=300)
        self.prompt_builder = PromptBuilder()

    async def generate_act(self, story_id: UUID, act_number: int) -> GeneratedAct:
        """Genera un acto específico de la historia ejecutando el pipeline completo."""
        
        # 1. Obtener contexto de la historia
        story = await self.repository.get_story(story_id)
        if not story:
            raise ValueError(f"Historia {story_id} no encontrada.")
        
        act_input = next((a for a in story.actos_input if a.number == act_number), None)
        if not act_input:
            raise ValueError(f"Acto {act_number} no definido en la historia.")

        # 2. Obtener estado previo
        previous_state = await self._get_previous_state(story_id, act_number)
        
        # 3. Construir Prompts
        system_prompt = self.prompt_builder.build_system_prompt(story)
        act_prompt = self.prompt_builder.build_act_prompt(story, act_input, previous_state)
        
        # 4. Llamada al LLM (Generación)
        raw_output = await self.llm.generate(
            prompt=act_prompt, 
            system_prompt=system_prompt,
            model="qwen2.5:32b"
        )
        
        # 5. Normalización (Limpieza técnica de tags <think>, etc.)
        clean_content = self.normalizer.normalize(raw_output)
        
        # 6. Validación de Calidad (Hito 2)
        # Lanza QualityValidationError si falla el mínimo de palabras o hay residuos
        self.validator.validate(clean_content)
        
        # 7. Extracción de Estado (Continuidad)
        new_state = await self._extract_new_state(clean_content, previous_state)
        
        # 8. Persistencia y Retorno
        generated_act = GeneratedAct(
            number=act_number,
            content=clean_content,
            raw_output=raw_output,
            word_count=len(clean_content.split()),
            state_after=new_state
        )
        
        await self.repository.save_act(story_id, generated_act)
        return generated_act

    async def _get_previous_state(self, story_id: UUID, act_number: int) -> Optional[NarrativeState]:
        """Recupera el estado narrativo del acto anterior."""
        if act_number <= 1:
            return None
            
        acts = await self.repository.get_acts(story_id)
        prev_act = next((a for a in acts if a.number == act_number - 1), None)
        return prev_act.state_after if prev_act else None

    async def _extract_new_state(self, content: str, previous: Optional[NarrativeState]) -> NarrativeState:
        """Extrae el nuevo estado narrativo usando el extractor si está disponible."""
        if self.state_extractor:
            return await self.state_extractor.extract_state(content, previous)
        return NarrativeState()
