"""Export router."""

import base64
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.application.services.observability_service import observability
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.renderers import MarkdownRenderer
from src.utils.timezone import now_argentina

router = APIRouter(tags=["Export"])

@router.post("/stories/{story_id}/export")
async def export_story(story_id: str) -> JSONResponse:
    """Export story to Markdown as base64."""
    story_repo = SQLStoryRepository()
    renderer = MarkdownRenderer()
    beat_repo = SQLBeatRepository()

    try:
        story = await story_repo.get_by_id(UUID(story_id))
    except Exception:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    beats = await beat_repo.get_by_story(UUID(story_id))
    story.beats = beats

    md = renderer.render(story)
    md_b64 = base64.b64encode(md.encode("utf-8")).decode("utf-8")

    timestamp = now_argentina().strftime("%Y%m%d%H%M")
    safe_title = "".join(c for c in story.title if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_").lower()
    filename = f"{safe_title}_{timestamp}.md"

    observability.record(
        category="export",
        message=f"Historia '{story.title}' exportada a Markdown",
        type="success",
        story_id=story_id,
        story_title=story.title
    )

    return JSONResponse(content={"filename": filename, "content_b64": md_b64})
