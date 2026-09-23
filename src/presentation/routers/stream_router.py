"""Stream router — SSE y endpoints de soporte (Spec-201)."""

import logging
from uuid import UUID

import aiosqlite
from fastapi import APIRouter, Header, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.application.services.job_manager import JobAlreadyActiveError
from src.application.services.observability_service import observability
from src.config import settings
from src.infrastructure.database.repositories import (
    SQLBeatRepository,
    SQLJobRepository,
    SQLStoryRepository,
)
from src.presentation.generation import submit_full_generation
from src.presentation.routers.job_router import parse_last_event_id, stream_job_events

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Streaming"])


# ── Hito 3: SSE endpoint ──────────────────────────────────────────────────────


@router.get("/stories/{story_id}/stream")
async def stream_generation(story_id: str, last_event_id: str | None = Header(None)):
    """SSE legado de la generación de una historia (Spec-201/230, sobre jobs Spec-460).

    - Si la historia tiene un job activo, se ata a su canal (replay + en vivo).
    - Spec-230 Sala Resiliente: `completed`/`failed` sin job activo → modo lectura
      con los beats históricos desde la DB.
    - Si no, arranca la generación como job (comportamiento legado; en Spec-460 S4
      la sala pasa a crear el job con POST y este endpoint queda de solo lectura).
    """
    from src.domain.models import StoryStatus
    from src.domain.streaming import StreamEvent, StreamEventType

    story_repo = SQLStoryRepository()
    story = await story_repo.get_by_id(UUID(story_id))

    if not story:
        logger.warning(f"SSE Request failed: Story {story_id} not found.")
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    job = await SQLJobRepository().get_active_for_story(story.id)
    logger.info(
        f"[STREAM] Inicio de petición SSE | Story: {story_id} | "
        f"Status actual: {story.status.value} | Job activo: {job.id if job else None}"
    )

    if job is None and story.status in (StoryStatus.COMPLETED, StoryStatus.FAILED):
        logger.info(f"[STREAM] Modo lectura para historia {story_id} ({story.status.value})")
        beats = await SQLBeatRepository().get_by_story(story.id)

        async def read_only_generator():
            yield StreamEvent(
                event=StreamEventType.STATUS,
                data={"msg": "Cargando beats históricos...", "step": "loading"},
            ).to_sse()
            for beat in beats:
                yield StreamEvent(
                    event=StreamEventType.BEAT_DONE,
                    data={"number": beat.number, "content": beat.generated_act},
                ).to_sse()
            yield StreamEvent(
                event=StreamEventType.DONE,
                data={
                    "story_id": str(story.id),
                    "total_beats": len(beats),
                    "read_only": True,
                },
            ).to_sse()

        return EventSourceResponse(read_only_generator())

    if job is None:
        try:
            job = await submit_full_generation(story)
        except JobAlreadyActiveError as exc:  # otra conexión ganó la carrera
            job = await SQLJobRepository().get(exc.job_id)

    return EventSourceResponse(stream_job_events(job, parse_last_event_id(last_event_id)))


# ── Hito 4a: /health mejorado ─────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    """Verifica conectividad con SQLite y el proveedor LLM activo."""
    checks: dict = {}

    # SQLite
    try:
        db_url = settings.database_url
        if db_url.startswith("sqlite+aiosqlite:///"):
            db_path = db_url[len("sqlite+aiosqlite:///") :]
        elif db_url.startswith("sqlite+aiosqlite://"):
            db_path = db_url[len("sqlite+aiosqlite://") :]
        else:
            db_path = db_url
        async with aiosqlite.connect(db_path) as db:
            await db.execute("SELECT 1")
        checks["sqlite"] = "ok"
    except Exception as exc:
        checks["sqlite"] = f"error: {exc}"

    # Proveedor LLM activo
    provider = settings.llm_provider
    checks["provider"] = provider

    if provider == "ollama":
        import httpx

        host = settings.ollama_host
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{host}/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else f"http {r.status_code}"
        except Exception as exc:
            checks["ollama"] = f"error: {exc}"

    elif provider == "anthropic":
        import os

        checks["anthropic_key"] = "present" if os.getenv("ANTHROPIC_API_KEY") else "missing"

    elif provider == "gemini":
        checks["gemini"] = "cli-based (no ping available)"

    healthy = checks.get("sqlite") == "ok" and (
        checks.get("ollama") == "ok" or provider in ("anthropic", "gemini", "mock")
    )

    return {
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
        "active_profile": settings.active_profile_name,
    }


# ── Hito 4b: /stories/{id}/full ──────────────────────────────────────────────


@router.get("/stories/{story_id}/full")
async def get_story_full(story_id: str):
    """Devuelve Story + Beats + NarrativeAnchors en una sola petición."""
    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()

    story = await story_repo.get_by_id(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    beats = await beat_repo.get_by_story(story.id)

    anchors_row = None
    try:
        anchors_row = await story_repo.get_narrative_anchors(story.id)
    except AttributeError:
        pass  # método aún no implementado en el repo

    return {
        "story": {
            "id": str(story.id),
            "title": story.title,
            "status": story.status.value,
            "protagonista": story.protagonista,
            "relator": story.relator,
            "sinopsis": story.sinopsis,
            "atmosfera": story.atmosfera,
            "created_at": story.created_at.isoformat(),
        },
        "beats": [
            {
                "number": b.number,
                "summary": b.summary,
                "content": b.generated_act,
                "status": b.status,
                "beat_type": b.beat_type.value if b.beat_type else None,
            }
            for b in beats
        ],
        "narrative_anchors": anchors_row,
    }


# ── Hito 4c: /config/active-profile ──────────────────────────────────────────


@router.get("/config/active-profile")
async def get_active_profile():
    """Devuelve el perfil LLM activo y su configuración de roles."""
    roles = {}
    for role in ("story_analyst", "director", "voz", "journal"):
        cfg = settings.role_config(role)
        roles[role] = {
            "model": cfg.get("model"),
            "temperature": cfg.get("temperature"),
        }

    return {
        "active_profile": settings.active_profile_name,
        "provider": settings.llm_provider,
        "roles": roles,
    }


@router.get("/system/events")
async def get_system_events(limit: int = 10):
    """Devuelve el historial de eventos del sistema."""
    return observability.get_history(limit)
