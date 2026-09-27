"""SQL ActText Repository."""

from datetime import datetime
from uuid import UUID

from src.domain.models import ActText
from src.infrastructure.database.connection import connection


class SQLBeatRepository:
    """SQLite repository para macro_beats.

    Spec-190 §4.4: las reglas activas ya no se persisten per-beat (tabla
    macro_beat_rule eliminada); se derivan determinísticamente desde
    `rule.applies_to_beat` al generar.
    """

    async def save(self, beat: ActText, story_id: UUID) -> ActText:
        """Persiste un macro_beat (upsert: actualiza o inserta)."""
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM macro_beat WHERE story_id = ? AND number = ?",
                (str(story_id), beat.number),
            )
            existing = await cursor.fetchone()

            status = beat.status.value if hasattr(beat.status, "value") else str(beat.status)
            if existing:
                await conn.execute(
                    """UPDATE macro_beat SET generated_act = ?, status = ?,
                    system_prompt = ?, user_prompt = ? WHERE story_id = ? AND number = ?""",
                    (
                        beat.generated_act,
                        status,
                        beat.system_prompt,
                        beat.user_prompt,
                        str(story_id),
                        beat.number,
                    ),
                )
            else:
                await conn.execute(
                    """INSERT INTO macro_beat
                    (story_id, number, generated_act, status, system_prompt, user_prompt)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        str(story_id),
                        beat.number,
                        beat.generated_act,
                        status,
                        beat.system_prompt,
                        beat.user_prompt,
                    ),
                )

            await conn.commit()
        return beat

    async def get_by_story(self, story_id: UUID) -> list[ActText]:
        """Retorna todos los macro_beats de una historia."""
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM macro_beat WHERE story_id = ? ORDER BY number",
                (str(story_id),),
            )
            rows = await cursor.fetchall()
        return [self._row_to_beat(row) for row in rows]

    async def get_by_number(self, story_id: UUID, number: int) -> ActText | None:
        """Retorna un macro_beat específico."""
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM macro_beat WHERE story_id = ? AND number = ?",
                (str(story_id), number),
            )
            row = await cursor.fetchone()

        if not row:
            return None
        return self._row_to_beat(row)

    async def update(self, beat: ActText, story_id: UUID) -> ActText:
        """Actualiza un macro_beat existente."""
        return await self.save(beat, story_id)

    def _row_to_beat(self, row) -> ActText:
        """Convierte una fila de macro_beat a la entidad ActText."""
        raw_created_at = row["created_at"] if "created_at" in row.keys() else None
        created_at = datetime.fromisoformat(raw_created_at) if raw_created_at else None
        return ActText(
            number=row["number"],
            generated_act=row["generated_act"] or "",
            status=row["status"],
            user_prompt=row["user_prompt"],
            system_prompt=row["system_prompt"],
            created_at=created_at,
        )
