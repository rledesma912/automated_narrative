"""SQL GeneratedNarrative Repository."""

import logging
from datetime import datetime
from uuid import UUID

from src.domain.models import GeneratedNarrative, StoryStatus
from src.infrastructure.database.connection import get_connection

logger = logging.getLogger(__name__)


class SQLGeneratedNarrativeRepository:
    """SQLite implementation of GeneratedNarrativeRepository."""

    async def save(self, narrative: GeneratedNarrative) -> GeneratedNarrative:
        """Save a generated narrative."""
        conn = await get_connection()
        await conn.execute(
            """INSERT OR REPLACE INTO generated_narrative
            (id, story_template_id, title, content, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(narrative.id),
                str(narrative.story_template_id),
                narrative.title,
                narrative.content,
                narrative.status.value,
                narrative.created_at.isoformat(),
            ),
        )
        await conn.commit()
        await conn.close()
        logger.debug(f"[GENERATED_NARRATIVE] Saved: {narrative.id}")
        return narrative

    async def get_by_id(self, narrative_id: UUID) -> GeneratedNarrative | None:
        """Get generated narrative by ID."""
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM generated_narrative WHERE id = ?",
            (str(narrative_id),),
        )
        row = await cursor.fetchone()
        await conn.close()

        if not row:
            return None

        return GeneratedNarrative(
            id=UUID(row["id"]),
            story_template_id=UUID(row["story_template_id"]),
            title=row["title"],
            content=row["content"],
            status=StoryStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def get_by_story_template_id(self, story_template_id: UUID) -> list[GeneratedNarrative]:
        """Get all generated narratives for a story template."""
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM generated_narrative WHERE story_template_id = ? ORDER BY created_at DESC",
            (str(story_template_id),),
        )
        rows = await cursor.fetchall()
        await conn.close()

        narratives = []
        for row in rows:
            narratives.append(
                GeneratedNarrative(
                    id=UUID(row["id"]),
                    story_template_id=UUID(row["story_template_id"]),
                    title=row["title"],
                    content=row["content"],
                    status=StoryStatus(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        return narratives

    async def delete(self, narrative_id: UUID) -> None:
        """Delete a generated narrative."""
        conn = await get_connection()
        await conn.execute(
            "DELETE FROM generated_narrative WHERE id = ?",
            (str(narrative_id),),
        )
        await conn.commit()
        await conn.close()
        logger.debug(f"[GENERATED_NARRATIVE] Deleted: {narrative_id}")

    async def delete_by_story_template_id(self, story_template_id: UUID) -> None:
        """Delete all generated narratives for a story template."""
        conn = await get_connection()
        await conn.execute(
            "DELETE FROM generated_narrative WHERE story_template_id = ?",
            (str(story_template_id),),
        )
        await conn.commit()
        await conn.close()
        logger.debug(f"[GENERATED_NARRATIVE] Deleted all for story_template: {story_template_id}")
