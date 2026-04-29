"""Stream router — SSE y endpoints de soporte (Spec-201)."""

import logging
from uuid import UUID

import aiosqlite
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.application.services import PromptBuilder
from src.application.services.streaming_service import stream_story
from src.application.use_cases.director_use_case import DirectorUseCase
from src.config import settings
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.infrastructure.normalizers import ResponseNormalizer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Streaming"])


# ── Hito 3: SSE endpoint ──────────────────────────────────────────────────────

@router.get("/stories/{story_id}/stream")
async def stream_generation(story_id: str):
    """Inicia la generación de una historia y emite eventos SSE en tiempo real.

    Idempotencia (punto 3): si la historia ya está en PROCESSING devuelve error inmediato.
    Heartbeat (punto 2): emitido cada 15s desde una tarea paralela durante la espera del LLM.
    Normalizer (punto 4): macro_beat.content ya viene normalizado desde VozUseCase.
    Eventos: status | beat_start | beat_done | heartbeat | done | error
    """
    story_repo = SQLStoryRepository()
    story = await story_repo.get_by_id(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    # Punto 3 — Idempotencia: bloquear si ya hay un proceso activo
    if story.status.value == "processing":
        raise HTTPException(
            status_code=409,
            detail="La historia ya está siendo generada. Espera a que termine o recarga para ver el progreso.",
        )

    llm            = LLMFactory.get_provider()
    prompt_builder = PromptBuilder()
    normalizer     = ResponseNormalizer()

    director = DirectorUseCase(
        llm=llm,
        prompt_builder=prompt_builder,
        normalizer=normalizer,
        story_repo=story_repo,
    )

    async def event_generator():
        async for event in stream_story(director, story, story_repo=story_repo):
            yield event.to_sse()

    return EventSourceResponse(event_generator())


# ── Hito 4a: /health mejorado ─────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Verifica conectividad con SQLite y el proveedor LLM activo."""
    checks: dict = {}

    # SQLite
    try:
        async with aiosqlite.connect("stories.db") as db:
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
        checks.get("ollama") == "ok"
        or provider in ("anthropic", "gemini", "mock")
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
    beat_repo  = SQLBeatRepository()

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
                "content": b.content,
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
