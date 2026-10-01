"""Spec-610: el paquete para el video (guion, la calabaza y el mapa de producción)."""

from fastapi import APIRouter

from src.application.services.video.config import video_config

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
