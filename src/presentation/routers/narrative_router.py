"""GeneratedNarrative router."""

import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response

from src.application.services import repetition_check
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


@router.get("/generated-narratives/{narrative_id}/repetition")
async def get_narrative_repetition(
    narrative_id: str,
    use_case: GenerateNarrativesUseCase = Depends(_narrative_use_case),
):
    """Spec-530 §8.3: frases que cada acto repite de uno anterior y clichés (sin LLM)."""
    try:
        nid = UUID(narrative_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de narrativa inválido")
    narrative = await use_case.get_by_id(nid)
    if not narrative:
        raise HTTPException(status_code=404, detail="Narrativa no encontrada")
    parts = re.split(r"^## Acto \d+\s*$", narrative.content, flags=re.M)
    acts = [p.strip() for p in parts[1:]] if len(parts) > 1 else [narrative.content]
    story = await SQLStoryRepository().get_by_id(narrative.story_template_id)
    known = _authoring_text(story) if story else None
    return {
        "acts": [
            {
                "number": r.number,
                "repeated": r.repeated,
                "cliches": r.cliches,
                "invented_names": r.invented_names,
            }
            for r in repetition_check.check(acts, known=known)
        ]
    }


def _authoring_text(story) -> str:
    """Todo lo que cargó el autor: de acá salen los nombres que la Voz puede usar."""
    parts = [story.title, story.sinopsis, story.protagonista]
    parts += [p.get("name", "") + " " + p.get("relation", "") for p in story.personajes_full]
    parts += [s.name + " " + s.description for s in story.scenarios]
    parts += [e.name + " " + e.description + " " + e.manifestations for e in story.entities]
    for act in story.outline:
        parts += [act.goal, act.scenario, *act.events, *act.on_stage]
    if story.direction:
        parts += [story.direction.premise, story.direction.ending]
    parts += [w.answer for w in story.workshop]
    return " ".join(p for p in parts if p)


@router.get("/generated-narratives/{narrative_id}/export.md")
async def export_narrative_markdown(
    narrative_id: str,
    use_case: GenerateNarrativesUseCase = Depends(_narrative_use_case),
):
    """Descarga el relato como `.md` para el TTS (Spec-490)."""
    try:
        nid = UUID(narrative_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de narrativa inválido")

    exported = await use_case.export_tts_markdown(nid)
    if not exported:
        raise HTTPException(status_code=404, detail="Narrativa no encontrada")

    filename, markdown = exported
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
