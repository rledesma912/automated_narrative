"""SQL MacroBeat Repository."""

from uuid import UUID

from src.domain.models import MacroBeat

# Alias público para código existente que importa Beat
Beat = MacroBeat


class SQLBeatRepository:
    """SQLite repository para macro_beats."""

    async def save(self, beat: MacroBeat, story_id: UUID) -> MacroBeat:
        """Persiste un macro_beat."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        await conn.execute(
            """INSERT OR REPLACE INTO macro_beat
            (story_id, number, summary, content, status, technical_context,
             active_scenario_id, narrative_context, memory_snapshot, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(story_id),
                beat.number,
                beat.summary,
                beat.content,
                beat.status,
                str(beat.technical_context) if beat.technical_context else None,
                beat.active_scenario_id,
                beat.narrative_context,
                beat.memory_snapshot,
                beat.created_at.isoformat(),
            ),
        )
        await conn.commit()
        await conn.close()
        return beat

    async def get_by_story(self, story_id: UUID) -> list[MacroBeat]:
        """Retorna todos los macro_beats de una historia, ordenados por número."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM macro_beat WHERE story_id = ? ORDER BY number",
            (str(story_id),),
        )
        rows = await cursor.fetchall()
        await conn.close()
        return [self._row_to_beat(row) for row in rows]

    async def get_by_number(self, story_id: UUID, number: int) -> MacroBeat | None:
        """Retorna un macro_beat específico por número."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM macro_beat WHERE story_id = ? AND number = ?",
            (str(story_id), number),
        )
        row = await cursor.fetchone()
        await conn.close()
        return self._row_to_beat(row) if row else None

    async def update(self, beat: MacroBeat, story_id: UUID) -> MacroBeat:
        """Actualiza un macro_beat existente."""
        return await self.save(beat, story_id)

    async def save_batch(self, beats: list[MacroBeat], story_id: UUID) -> list[MacroBeat]:
        """Persiste múltiples macro_beats."""
        for beat in beats:
            await self.save(beat, story_id)
        return beats

    def _row_to_beat(self, row) -> MacroBeat:
        return MacroBeat(
            number=row["number"],
            summary=row["summary"],
            content=row["content"] or "",
            status=row["status"],
            active_scenario_id=row["active_scenario_id"],
            narrative_context=row["narrative_context"],
            memory_snapshot=row["memory_snapshot"],
        )
