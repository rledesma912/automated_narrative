"""GeneratedNarrative router."""

import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response

from src.application.services import narrative_acts, repetition_check
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.infrastructure.database.repositories import SQLJobRepository, SQLStoryRepository
from src.messages import message
from src.presentation.schemas.request import ActTextUpdateRequest
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
    """Spec-530 §8.3: frases que cada acto repite de uno anterior y clichés (sin LLM).

    Spec-590 F: también oraciones cortadas (`too_cut` desde el 25 %) y diálogo directo.
    """
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
                "repeated": [message("repeticion.frase", frase=f, acto=a) for f, a in r.repeated],
                "cliches": r.cliches,
                "invented_names": r.invented_names,
                "cut_sentences": r.cut_sentences,
                "cut_count": r.cut_count,
                "cut_pct": r.cut_pct,
                "too_cut": r.too_cut,
                "dialogue": r.dialogue,
            }
            for r in repetition_check.check(acts, known=known)
        ]
    }


@router.put("/generated-narratives/{narrative_id}/acts/{number}")
async def update_narrative_act(
    narrative_id: str,
    number: int,
    request: ActTextUpdateRequest,
    use_case: GenerateNarrativesUseCase = Depends(_narrative_use_case),
):
    """Spec-610 T1.2: corrige el texto de un acto del relato; los demás no se tocan.

    El control de repetición (`GET …/repetition`) se calcula sobre lo corregido.
    """
    try:
        nid = UUID(narrative_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de narrativa inválido")
    narrative = await use_case.get_by_id(nid)
    if not narrative:
        raise HTTPException(status_code=404, detail="Narrativa no encontrada")
    if number not in narrative_acts.split(narrative.content).acts:
        raise HTTPException(status_code=404, detail=message("api.relato_sin_acto", acto=number))
    if not narrative_acts.normalize(request.text):
        raise HTTPException(status_code=422, detail=message("api.acto_vacio"))
    active = await SQLJobRepository().get_active_for_story(narrative.story_template_id)
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=message("api.ia_trabajando"),
            headers={"X-Job-Id": str(active.id)},
        )
    saved = await use_case.update_act(nid, number, request.text)
    text = narrative_acts.split(saved.content).acts[number]
    return {
        "number": number,
        "text": text,
        "paragraphs": len(narrative_acts.paragraphs(text)),
        "words": len(text.split()),
    }


def _authoring_text(story) -> str:
    return repetition_check.known_text(story)


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
