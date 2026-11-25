"""SQL repository de la miniatura de cada historia (Spec-790)."""

from uuid import UUID

from src.domain.thumbnail import Thumbnail
from src.infrastructure.database.connection import connection
from src.utils.timezone import now_argentina


class SQLThumbnailRepository:
    """Una miniatura por historia, en JSON; se borra con la historia."""

    async def get(self, story_id: UUID | str) -> Thumbnail | None:
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT data FROM thumbnail WHERE story_id = ?", (str(story_id),)
            )
            row = await cursor.fetchone()
        return Thumbnail.model_validate_json(row["data"]) if row else None

    async def save(self, thumb: Thumbnail) -> Thumbnail:
        thumb.updated_at = now_argentina()
        async with connection() as conn:
            await conn.execute(
                """INSERT INTO thumbnail (story_id, data, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(story_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
                (thumb.story_id, thumb.model_dump_json(), thumb.updated_at.isoformat()),
            )
            await conn.commit()
        return thumb

    async def story_ids(self) -> set[str]:
        async with connection() as conn:
            cursor = await conn.execute("SELECT story_id FROM thumbnail")
            rows = await cursor.fetchall()
        return {row["story_id"] for row in rows}
