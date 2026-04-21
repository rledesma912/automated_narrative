"""SQL NarrativeAnchors Repository."""

import uuid
from uuid import UUID

from src.domain.models import NarrativeAnchors


class SQLNarrativeAnchorsRepository:
    """SQLite repository para los anclajes narrativos de una historia."""

    async def save(self, anchors: NarrativeAnchors) -> NarrativeAnchors:
        """Persiste los anclajes narrativos (INSERT OR REPLACE)."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        await conn.execute(
            """INSERT OR REPLACE INTO narrative_anchors
            (id, story_id, initial_state, threat_nature, horror_peak, spatial_anchor)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                str(anchors.story_id),
                anchors.initial_state,
                anchors.threat_nature,
                anchors.horror_peak,
                anchors.spatial_anchor,
            ),
        )
        await conn.commit()
        await conn.close()
        return anchors

    async def get_by_story(self, story_id: UUID) -> NarrativeAnchors | None:
        """Retorna los anclajes narrativos de una historia, o None si no existen."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM narrative_anchors WHERE story_id = ?",
            (str(story_id),),
        )
        row = await cursor.fetchone()
        await conn.close()
        if not row:
            return None
        return NarrativeAnchors(
            story_id=UUID(row["story_id"]),
            initial_state=row["initial_state"],
            threat_nature=row["threat_nature"],
            horror_peak=row["horror_peak"],
            spatial_anchor=row["spatial_anchor"],
        )
