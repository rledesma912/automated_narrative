"""SQL Story Repository."""

from uuid import UUID

from src.domain.models import NarrativeJournal, Story, StoryStatus
from src.infrastructure.database.connection import get_connection


class SQLStoryRepository:
    """SQLite implementation of StoryRepository."""

    async def save(self, story: Story) -> Story:
        """Save a story."""
        conn = await get_connection()

        await conn.execute(
            """INSERT OR REPLACE INTO story
            (id, title, protagonista, relator, escenarios, sinopsis, atmosfera, narrative_brief, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(story.id),
                story.title,
                story.protagonista,
                story.relator,
                story.escenarios,
                story.sinopsis,
                story.atmosfera,
                story.narrative_brief,
                story.status.value,
                story.created_at.isoformat(),
            ),
        )

        await conn.commit()
        await conn.close()

        return story

    async def get_by_id(self, story_id: UUID) -> Story | None:
        """Get story by ID."""
        conn = await get_connection()

        cursor = await conn.execute(
            "SELECT * FROM story WHERE id = ?",
            (str(story_id),),
        )

        row = await cursor.fetchone()
        await conn.close()

        if not row:
            return None

        return self._row_to_story(row)

    async def get_by_string_id(self, story_id: str) -> Story | None:
        """Get story by string ID (e.g., 'el_monte_prohibido_1744742400')."""
        conn = await get_connection()

        cursor = await conn.execute(
            "SELECT * FROM story WHERE id = ?",
            (story_id,),
        )

        row = await cursor.fetchone()
        await conn.close()

        if not row:
            return None

        return self._row_to_story(row)

    async def update(self, story: Story) -> Story:
        """Update a story."""
        return await self.save(story)

    async def delete(self, story_id: UUID) -> None:
        """Delete a story."""
        conn = await get_connection()

        await conn.execute("DELETE FROM beat WHERE story_id = ?", (str(story_id),))
        await conn.execute("DELETE FROM story WHERE id = ?", (str(story_id),))
        await conn.execute("DELETE FROM narrative_journal WHERE story_id = ?", (str(story_id),))

        await conn.commit()
        await conn.close()

    async def list_all(self) -> list[Story]:
        """List all stories."""
        conn = await get_connection()

        cursor = await conn.execute("SELECT * FROM story ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        await conn.close()

        return [self._row_to_story(row) for row in rows]

    async def save_journal(self, story_id: UUID, journal: NarrativeJournal) -> None:
        """Save or update the narrative journal for a story."""
        conn = await get_connection()

        await conn.execute(
            """INSERT OR REPLACE INTO narrative_journal
            (story_id, last_events, unresolved_mysteries, physical_emotional_state)
            VALUES (?, ?, ?, ?)""",
            (
                str(story_id),
                journal.last_events,
                journal.unresolved_mysteries,
                journal.physical_emotional_state,
            ),
        )

        await conn.commit()
        await conn.close()

    async def get_journal(self, story_id: UUID) -> NarrativeJournal | None:
        """Get the narrative journal for a story."""
        conn = await get_connection()

        cursor = await conn.execute(
            "SELECT * FROM narrative_journal WHERE story_id = ?",
            (str(story_id),),
        )

        row = await cursor.fetchone()
        await conn.close()

        if not row:
            return None

        return NarrativeJournal(
            last_events=row["last_events"],
            unresolved_mysteries=row["unresolved_mysteries"],
            physical_emotional_state=row["physical_emotional_state"],
        )

    async def save_narrative_brief(self, story_id, brief: str) -> None:
        """Persiste el narrative_brief generado por el expansor."""
        conn = await get_connection()
        await conn.execute(
            "UPDATE story SET narrative_brief = ? WHERE id = ?",
            (brief, str(story_id)),
        )
        await conn.commit()
        await conn.close()

    def _row_to_story(self, row) -> Story:
        """Convert row to Story."""
        return Story(
            id=UUID(row["id"]),
            title=row["title"],
            protagonista=row["protagonista"],
            relator=row["relator"],
            escenarios=row["escenarios"],
            sinopsis=row["sinopsis"],
            atmosfera=row["atmosfera"],
            narrative_brief=row["narrative_brief"] or "",
            status=StoryStatus(row["status"]),
        )
