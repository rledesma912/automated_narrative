"""GeneratedNarrative router."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.infrastructure.database.repositories import SQLStoryRepository
from src.presentation.schemas.response import GeneratedNarrativeResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["GeneratedNarratives"])


def _narrative_use_case() -> GenerateNarrativesUseCase:
    return GenerateNarrativesUseCase()


def _story_repo() -> SQLStoryRepository:
    return SQLStoryRepository()


@router.post(
    "/story-templates/{story_template_id}/generate-narrative",
    response_model=GeneratedNarrativeResponse,
)
async def generate_narrative(
    story_template_id: str,
    title: str,
    use_case: GenerateNarrativesUseCase = Depends(_narrative_use_case),
):
    """Genera un nuevo relato a partir de los beats existentes de una plantilla."""
    try:
        story_id = UUID(story_template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de plantilla inválido")

    try:
        narrative = await use_case.generate_from_existing_beats(story_id, title)
        return GeneratedNarrativeResponse(
            id=str(narrative.id),
            story_template_id=str(narrative.story_template_id),
            title=narrative.title,
            content=narrative.content,
            status=narrative.status.value,
            created_at=narrative.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generando narrativa: {e}")
        raise HTTPException(status_code=500, detail="Error al generar narrativa")


@router.get(
    "/story-templates/{story_template_id}/narratives",
    response_model=list[GeneratedNarrativeResponse],
)
async def list_narratives(
    story_template_id: str,
    use_case: GenerateNarrativesUseCase = Depends(_narrative_use_case),
):
    """Lista todos los relatos generados para una plantilla."""
    try:
        story_id = UUID(story_template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de plantilla inválido")

    narratives = await use_case.list_by_story_template(story_id)
    return [
        GeneratedNarrativeResponse(
            id=str(n.id),
            story_template_id=str(n.story_template_id),
            title=n.title,
            content=n.content,
            status=n.status.value,
            created_at=n.created_at.isoformat(),
        )
        for n in narratives
    ]


@router.get(
    "/generated-narratives/{narrative_id}",
    response_model=GeneratedNarrativeResponse,
)
async def get_narrative(
    narrative_id: str,
    use_case: GenerateNarrativesUseCase = Depends(_narrative_use_case),
):
    """Obtiene un relato generado por su ID."""
    try:
        nid = UUID(narrative_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de narrativa inválido")

    narrative = await use_case.get_by_id(nid)
    if not narrative:
        raise HTTPException(status_code=404, detail="Narrativa no encontrada")

    return GeneratedNarrativeResponse(
        id=str(narrative.id),
        story_template_id=str(narrative.story_template_id),
        title=narrative.title,
        content=narrative.content,
        status=narrative.status.value,
        created_at=narrative.created_at.isoformat(),
    )


@router.get("/generated-narratives/{narrative_id}/text")
async def get_narrative_text(
    narrative_id: str,
    use_case: GenerateNarrativesUseCase = Depends(_narrative_use_case),
):
    """Obtiene solo el texto de un relato generado (para copiar)."""
    try:
        nid = UUID(narrative_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de narrativa inválido")

    narrative = await use_case.get_by_id(nid)
    if not narrative:
        raise HTTPException(status_code=404, detail="Narrativa no encontrada")

    return JSONResponse(content={"text": narrative.content})


@router.delete("/generated-narratives/{narrative_id}")
async def delete_narrative(
    narrative_id: str,
    use_case: GenerateNarrativesUseCase = Depends(_narrative_use_case),
):
    """Elimina un relato generado."""
    try:
        nid = UUID(narrative_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de narrativa inválido")

    await use_case.delete(nid)
    return {"message": "Narrativa eliminada"}
