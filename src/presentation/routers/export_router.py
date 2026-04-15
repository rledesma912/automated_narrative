"""Export router."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["Export"])


@router.get("/stories/{story_id}/export")
async def export_story(story_id: str) -> PlainTextResponse:
    """Export story to Markdown."""
    from src.infrastructure.database.repositories import SQLStoryRepository
    from src.infrastructure.renderers import MarkdownRenderer

    story_repo = SQLStoryRepository()
    renderer = MarkdownRenderer()

    try:
        story = await story_repo.get_by_id(UUID(story_id))
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Historia no encontrada: {story_id}"
        )

    if not story:
        raise HTTPException(
            status_code=404, detail=f"Historia no encontrada: {story_id}"
        )

    from src.infrastructure.database.repositories import SQLBeatRepository

    beat_repo = SQLBeatRepository()
    beats = await beat_repo.get_by_story(UUID(story_id))
    story.beats = beats

    md = renderer.render(story)

    return PlainTextResponse(content=md, media_type="text/markdown")
