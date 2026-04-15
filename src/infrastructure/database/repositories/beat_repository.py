"""SQL Beat Repository."""

from uuid import UUID

from src.domain.models import Beat
from src.infrastructure.database.connection import get_connection


class SQLBeatRepository:
    """SQLite implementation of BeatRepository."""

    async def save(self, beat: Beat, story_id: UUID) -> Beat:
        """Save a beat."""
        conn = await get_connection()

        await conn.execute(
            """INSERT OR REPLACE INTO beat 
            (story_id, number, summary, content, status, technical_context, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(story_id),
                beat.number,
                beat.summary,
                beat.content,
                beat.status,
                str(beat.technical_context) if beat.technical_context else None,
                beat.created_at.isoformat(),
            ),
        )

        await conn.commit()
        await conn.close()

        return beat

    async def get_by_story(self, story_id: UUID) -> list[Beat]:
        """Get all beats for a story."""
        conn = await get_connection()

        cursor = await conn.execute(
            "SELECT * FROM beat WHERE story_id = ? ORDER BY number",
            (str(story_id),),
        )

        rows = await cursor.fetchall()
        await conn.close()

        return [self._row_to_beat(row) for row in rows]

    async def get_by_number(self, story_id: UUID, number: int) -> Beat | None:
        """Get beat by number."""
        conn = await get_connection()

        cursor = await conn.execute(
            "SELECT * FROM beat WHERE story_id = ? AND number = ?",
            (str(story_id), number),
        )

        row = await cursor.fetchone()
        await conn.close()

        if not row:
            return None

        return self._row_to_beat(row)

    async def update(self, beat: Beat, story_id: UUID) -> Beat:
        """Update a beat."""
        return await self.save(beat, story_id)

    async def save_batch(self, beats: list[Beat], story_id: UUID) -> list[Beat]:
        """Save multiple beats."""
        for beat in beats:
            await self.save(beat, story_id)
        return beats

    def _row_to_beat(self, row) -> Beat:
        """Convert row to Beat."""
        return Beat(
            number=row["number"],
            summary=row["summary"],
            content=row["content"],
            status=row["status"],
        )
