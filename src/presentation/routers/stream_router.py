"""Stream router — SSE y endpoints de soporte (Spec-201)."""

import logging
from uuid import UUID

import aiosqlite
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.application.services import PromptBuilder
from src.application.services.observability_service import observability
from src.application.services.stream_session_manager import manager as session_manager
from src.application.services.streaming_service import stream_story
from src.application.use_cases.director_use_case import DirectorUseCase
from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase
from src.config import settings
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.infrastructure.normalizers import ResponseNormalizer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Streaming"])


# ── Hito 3: SSE endpoint ──────────────────────────────────────────────────────


@router.get("/stories/{story_id}/stream")
async def stream_generation(story_id: str):
    """Inicia (o se ata a) la generación SSE de una historia.

    Spec-230: Sala Resiliente - Si la historia está en estado completed o failed,
    el stream funciona en modo lectura: emite los beats históricos desde la DB
    sin intentar regenerar.

    Spec-220: idempotencia real vía StreamSessionManager. La primera request
    arranca el productor único; las siguientes se atan a la misma sesión y
    reciben el replay buffer + flujo en vivo. Cero riesgo de doble pipeline.
    """
    from src.domain.models import StoryStatus
    from src.domain.streaming import StreamEvent, StreamEventType

    story_repo = SQLStoryRepository()
    story = await story_repo.get_by_id(UUID(story_id))

    if not story:
        logger.warning(f"SSE Request failed: Story {story_id} not found.")
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    logger.info(
        f"[STREAM] Inicio de petición SSE | Story: {story_id} | "
        f"Status actual: {story.status.value} | "
        f"Sesión activa: {session_manager.is_active(story_id)}"
    )

    beat_repo = SQLBeatRepository()

    if story.status in (StoryStatus.COMPLETED, StoryStatus.FAILED):
        logger.info(f"[STREAM] Modo lectura para historia {story_id} ({story.status.value})")
        beats = await beat_repo.get_by_story(story.id)

        async def read_only_generator():
            yield StreamEvent(
                event=StreamEventType.STATUS,
                data={"msg": "Cargando beats históricos...", "step": "loading"},
            ).to_sse()
            for beat in beats:
                yield StreamEvent(
                    event=StreamEventType.BEAT_DONE,
                    data={"number": beat.number, "content": beat.content},
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

    observability.record(
        category="generation",
        message=f"Iniciando generación de '{story.title}'",
        story_id=story_id,
        story_title=story.title,
    )

    def _producer_factory():
        """Construye el productor único (solo se invoca en la primera attach por story_id)."""
        llm = LLMFactory.get_provider()
        prompt_builder = PromptBuilder()
        normalizer = ResponseNormalizer()
        director = DirectorUseCase(
            llm=llm,
            prompt_builder=prompt_builder,
            normalizer=normalizer,
            story_repo=story_repo,
        )
        return stream_story(
            director,
            story,
            story_repo=story_repo,
            beat_repo=beat_repo,
            narrative_use_case=GenerateNarrativesUseCase(),
        )

    queue, replay = await session_manager.attach(story_id, _producer_factory)

    async def event_generator():
        try:
            for event in replay:
                yield event.to_sse()
            while True:
                event = await queue.get()
                yield event.to_sse()
                if event.event.value in ("done", "stream_error"):
                    break
        finally:
            await session_manager.detach(story_id, queue)

    return EventSourceResponse(event_generator())


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


@router.get("/system/events")
async def get_system_events(limit: int = 10):
    """Devuelve el historial de eventos del sistema."""
    return observability.get_history(limit)
