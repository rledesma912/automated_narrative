"""Stream router — SSE y endpoints de soporte (Spec-201)."""

import logging
from uuid import UUID

import aiosqlite
import httpx
from fastapi import APIRouter, Header, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.config import settings, use_profile
from src.infrastructure.database.repositories import (
    SQLBeatRepository,
    SQLJobRepository,
    SQLStoryRepository,
)
from src.messages import message
from src.presentation.routers.beat_router import outline_summaries
from src.presentation.routers.job_router import parse_last_event_id, stream_job_events

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Streaming"])


# ── Hito 3: SSE endpoint ──────────────────────────────────────────────────────


@router.get("/stories/{story_id}/stream")
async def stream_generation(story_id: str, last_event_id: str | None = Header(None)):
    """SSE de solo lectura de una historia (Spec-201/230; Spec-460 S4).

    Nunca arranca trabajo: la generación se lanza con `POST /stories/{id}/jobs`.
    - Con un job activo: se ata a su canal (replay + en vivo).
    - Sin job activo: reproduce los beats históricos desde la DB (Spec-230) y cierra
      con `done` si la historia está completa, o `stream_error` si no hay nada en curso.
    """
    from src.domain.models import StoryStatus
    from src.domain.streaming import StreamEvent, StreamEventType

    story = await SQLStoryRepository().get_by_id(UUID(story_id))
    if not story:
        logger.warning(f"SSE Request failed: Story {story_id} not found.")
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    job = await SQLJobRepository().get_active_for_story(story.id)
    logger.info(
        f"[STREAM] Petición SSE | Story: {story_id} | Status: {story.status.value} | "
        f"Job activo: {job.id if job else None}"
    )
    if job is not None:
        return EventSourceResponse(stream_job_events(job, parse_last_event_id(last_event_id)))

    beats = await SQLBeatRepository().get_by_story(story.id)

    async def read_only_generator():
        yield StreamEvent(
            event=StreamEventType.STATUS,
            data={"msg": "Cargando beats históricos...", "step": "loading"},
        ).to_sse()
        for beat in beats:
            if beat.generated_act:
                yield StreamEvent(
                    event=StreamEventType.BEAT_DONE,
                    data={"number": beat.number, "content": beat.generated_act},
                ).to_sse()
        if story.status == StoryStatus.COMPLETED:
            yield StreamEvent(
                event=StreamEventType.DONE,
                data={"story_id": str(story.id), "total_beats": len(beats), "read_only": True},
            ).to_sse()
        else:
            yield StreamEvent(
                event=StreamEventType.ERROR,
                data={"msg": message("api.sin_generacion_en_curso")},
            ).to_sse()

    return EventSourceResponse(read_only_generator())


# ── Hito 4a: /health mejorado ─────────────────────────────────────────────────


def _profiles_by_structure() -> dict[str, str | None]:
    """Spec-740 D4: el perfil de cada largo (None = deshabilitado)."""
    return {sid: settings.profile_for(sid) for sid in BeatSpecRepository().structure_ids}


def _providers_of(profile_names: set[str]) -> set[str]:
    """Proveedores que usan los roles de estos perfiles."""
    providers: set[str] = set()
    for name in profile_names:
        use_profile(name)
        try:
            providers |= settings.llm_providers
        finally:
            use_profile(None)
    return providers


async def _freellmapi_check() -> str:
    """Spec-740 A6: el gateway y la clave, con un pedido que no gasta cuota."""
    if not settings.freellmapi_api_key:
        return "missing key"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                f"{settings.freellmapi_url}/v1/models",
                headers={"Authorization": f"Bearer {settings.freellmapi_api_key}"},
            )
    except httpx.HTTPError as exc:
        return f"error: {type(exc).__name__}"
    return "ok" if r.status_code == 200 else f"http {r.status_code}"


OPENAI_MODELS_URL = "https://api.openai.com/v1/models"


async def _openai_check() -> str:
    """Spec-740 F5: la clave de OpenAI, con un pedido que no gasta (listar modelos)."""
    if not settings.openai_api_key:
        return "missing key"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                OPENAI_MODELS_URL,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
    except httpx.HTTPError as exc:
        return f"error: {type(exc).__name__}"
    return "ok" if r.status_code == 200 else f"http {r.status_code}"


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

    # Proveedores LLM en uso (Spec-480: cada rol puede tener el suyo), de todos los
    # perfiles que pueden correr (Spec-740 D4: uno por largo).
    profiles = _profiles_by_structure()
    providers = sorted(_providers_of({p for p in profiles.values() if p}))
    checks["provider"] = settings.llm_provider  # el del perfil (compatibilidad)
    checks["providers"] = providers

    if "ollama" in providers:
        host = settings.ollama_host
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{host}/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else f"http {r.status_code}"
        except Exception as exc:
            checks["ollama"] = f"error: {exc}"

    if "anthropic" in providers:
        # settings lee el .env: os.getenv no ve la clave si solo está ahí.
        checks["anthropic_key"] = "present" if settings.anthropic_api_key else "missing"

    if "freellmapi" in providers:
        checks["freellmapi"] = await _freellmapi_check()

    if "openai" in providers:
        checks["openai"] = await _openai_check()

    if "gemini" in providers:
        checks["gemini"] = "cli-based (no ping available)"

    provider_ok = {
        "ollama": checks.get("ollama") == "ok",
        "anthropic": checks.get("anthropic_key") == "present",
        "freellmapi": checks.get("freellmapi") == "ok",
        "openai": checks.get("openai") == "ok",
    }
    healthy = checks.get("sqlite") == "ok" and all(provider_ok.get(p, True) for p in providers)

    return {
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
        "active_profile": settings.active_profile_name,
        "profiles": profiles,
    }


# ── Hito 4b: /stories/{id}/full ──────────────────────────────────────────────


@router.get("/stories/{story_id}/full")
async def get_story_full(story_id: str):
    """Devuelve Story + Beats en una sola petición."""
    story_repo = SQLStoryRepository()
    beat_repo = SQLBeatRepository()

    story = await story_repo.get_by_id(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    beats = await beat_repo.get_by_story(story.id)
    summaries = outline_summaries(story)

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
                "summary": summaries.get(b.number, ""),
                "content": b.generated_act,
                "status": b.status,
            }
            for b in beats
        ],
    }


# ── Hito 4c: /config/active-profile ──────────────────────────────────────────


@router.get("/config/active-profile")
async def get_active_profile():
    """Devuelve el perfil LLM activo y su configuración de roles."""
    roles = {}
    for role in ("consultor", "planificador", "verificador", "voz", "journal", "guion", "revisor"):
        if role == "revisor" and not settings.has_role(role):
            continue  # Spec-700 D25: sin el rol no hay Revisor (queda la nota)
        cfg = settings.role_config(role)
        roles[role] = {
            "provider": settings.role_provider(role),
            "model": cfg.get("model"),
            "temperature": cfg.get("temperature"),
        }

    return {
        "active_profile": settings.active_profile_name,
        "provider": settings.llm_provider,
        "roles": roles,
        "profiles": _profiles_by_structure(),  # Spec-740 D4
    }
