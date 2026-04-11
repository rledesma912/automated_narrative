from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from uuid import UUID, uuid4
from src.presentation.schemas.story_schemas import GenerateStoryRequest, StoryResponse
from src.domain.models import Story, ActInput, StoryStatus
from src.infrastructure.database.repository import SQLiteStoryRepository
from src.infrastructure.adapters.ollama_adapter import OllamaAdapter
from src.infrastructure.adapters.state_extractor import OllamaStateExtractor
from src.infrastructure.normalizers.response_normalizer import LLMResponseNormalizer
from src.application.use_cases.generate_story import GenerateStoryUseCase
from src.config import settings

router = APIRouter()

# --- Inyección de Dependencias Manual para Simplicidad (Patrón Factory) ---
async def get_repository():
    # Usamos la URL de DB de settings
    # Nota: El path real suele ser algo como "stories.db"
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    repo = SQLiteStoryRepository(db_path)
    await repo.initialize()
    return repo

async def get_use_case(repo: SQLiteStoryRepository = Depends(get_repository)):
    llm = OllamaAdapter()
    normalizer = LLMResponseNormalizer()
    extractor = OllamaStateExtractor(llm=llm)
    return GenerateStoryUseCase(
        llm=llm,
        repository=repo,
        normalizer=normalizer,
        state_extractor=extractor
    )

# --- Endpoints REST ---

@router.post("/generate", response_model=StoryResponse)
async def start_generation(
    request: GenerateStoryRequest, 
    use_case: GenerateStoryUseCase = Depends(get_use_case)
):
    """Inicia un nuevo job de generación guardando la historia en la DB."""
    
    # 1. Mapear de Schema a Dominio
    story_id = uuid4()
    story = Story(
        id=story_id,
        title=request.title,
        protagonistas=request.protagonistas,
        relator=request.relator,
        escenarios=request.escenarios,
        sinopsis=request.sinopsis,
        atmosfera=request.atmosfera,
        reglas=request.reglas,
        actos_input=[ActInput(**a.model_dump()) for a in request.actos_input]
    )
    
    # 2. Guardar historia inicial
    await use_case.repository.save_story(story)
    
    return story

# --- WebSocket para Reporte en Tiempo Real ---

@router.websocket("/ws/jobs/{story_id}")
async def job_progress(
    websocket: WebSocket, 
    story_id: UUID,
    use_case: GenerateStoryUseCase = Depends(get_use_case)
):
    """Reporta el progreso de generación acto por acto vía WebSocket."""
    await websocket.accept()
    
    try:
        # Recuperar historia para saber cuántos actos tiene
        story = await use_case.repository.get_story(story_id)
        if not story:
            await websocket.send_json({"error": "Story not found"})
            await websocket.close()
            return

        await websocket.send_json({
            "event": "job_started", 
            "story_id": str(story_id),
            "total_acts": len(story.actos_input)
        })

        # Generar cada acto de forma secuencial
        for act_input in story.actos_input:
            await websocket.send_json({"event": "act_started", "act_number": act_input.number})
            
            # Orquestación del pipeline (Generar -> Normalizar -> Validar -> Extraer -> Guardar)
            act = await use_case.generate_act(story_id, act_input.number)
            
            await websocket.send_json({
                "event": "act_completed",
                "act_number": act.number,
                "word_count": act.word_count,
                "preview": act.content[:200] + "..."
            })

        await websocket.send_json({"event": "job_completed", "story_id": str(story_id)})
        
    except WebSocketDisconnect:
        # El cliente se desconectó
        pass
    except Exception as e:
        await websocket.send_json({"event": "job_failed", "error": str(e)})
    finally:
        await websocket.close()
