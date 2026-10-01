"""Spec-610: el paquete para el video (guion, la calabaza y el mapa de producción)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.application.services.video.config import video_config
from src.infrastructure.database.repositories import SQLVideoScriptRepository
from src.messages import message

router = APIRouter(tags=["Video"])


@router.get("/video/lectura")
async def get_reading_settings() -> dict:
    """Ritmo de lectura y largo del episodio (`config/video/lectura.yaml`): la web hace
    las mismas cuentas que el Core con estos valores."""
    lectura = video_config().lectura
    return {
        "palabras_por_minuto": lectura.palabras_por_minuto,
        "episodio_minutos": lectura.episodio_minutos.model_dump(),
    }


@router.get("/generated-narratives/{narrative_id}/video-script")
async def get_video_script(narrative_id: str) -> dict:
    """El paquete de la variante (404 si todavía no se armó)."""
    try:
        nid = UUID(narrative_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de narrativa inválido")
    script = await SQLVideoScriptRepository().get_by_narrative(nid)
    if script is None:
        raise HTTPException(status_code=404, detail=message("video.sin_paquete"))
    return script.model_dump(mode="json")
