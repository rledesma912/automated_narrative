"""SQL MacroBeat Repository."""

from datetime import datetime
from uuid import UUID

from src.domain.models import BeatType, MacroBeat
from src.infrastructure.database.connection import connection

# Alias público para código existente que importa Beat
Beat = MacroBeat


class SQLBeatRepository:
    """SQLite repository para macro_beats.

    Spec-190 §4.4: las reglas activas ya no se persisten per-beat (tabla
    macro_beat_rule eliminada); se derivan determinísticamente desde
    `rule.applies_to_beat` al generar.
    """

    async def save(self, beat: MacroBeat, story_id: UUID) -> MacroBeat:
        """Persiste un macro_beat (upsert: actualiza o inserta)."""
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM macro_beat WHERE story_id = ? AND number = ?",
                (str(story_id), beat.number),
            )
            existing = await cursor.fetchone()

            if existing:
                await conn.execute(
                    """UPDATE macro_beat SET
                    generated_act = ?,
                    status = ?,
                    active_scenario_id = ?,
                    active_scenario_description = ?,
                    system_prompt = ?,
                    user_prompt = ?
                    WHERE story_id = ? AND number = ?""",
                    (
                        beat.generated_act,
                        beat.status.value if hasattr(beat.status, "value") else str(beat.status),
                        beat.active_scenario_id,
                        beat.active_scenario_description,
                        beat.system_prompt,
                        beat.user_prompt,
                        str(story_id),
                        beat.number,
                    ),
                )
            else:
                await conn.execute(
                    """INSERT INTO macro_beat
                    (story_id, number, summary, synopsis_beat, generated_act, status,
                     active_scenario_id, active_scenario_description,
                     system_prompt, user_prompt, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(story_id),
                        beat.number,
                        beat.summary,
                        beat.synopsis_beat or "",
                        beat.generated_act,
                        beat.status.value if hasattr(beat.status, "value") else str(beat.status),
                        beat.active_scenario_id,
                        beat.active_scenario_description,
                        beat.system_prompt,
                        beat.user_prompt,
                        beat.beat_type.value
                        if beat.beat_type and hasattr(beat.beat_type, "value")
                        else (beat.beat_type or None),
                    ),
                )

            await conn.commit()
        return beat

    async def get_by_story(self, story_id: UUID) -> list[MacroBeat]:
        """Retorna todos los macro_beats de una historia."""
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM macro_beat WHERE story_id = ? ORDER BY number",
                (str(story_id),),
            )
            rows = await cursor.fetchall()
        return [self._row_to_beat(row) for row in rows]

    async def get_by_number(self, story_id: UUID, number: int) -> MacroBeat | None:
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

    async def update(self, beat: MacroBeat, story_id: UUID) -> MacroBeat:
        """Actualiza un macro_beat existente."""
        return await self.save(beat, story_id)

    def _row_to_beat(self, row) -> MacroBeat:
        """Convierte una fila de macro_beat a la entidad MacroBeat."""
        raw_type = row["type"] if "type" in row.keys() else None
        raw_created_at = row["created_at"] if "created_at" in row.keys() else None
        created_at = datetime.fromisoformat(raw_created_at) if raw_created_at else None
        return MacroBeat(
            number=row["number"],
            summary=row["summary"],
            generated_act=row["generated_act"] or "",
            status=row["status"],
            active_scenario_id=row["active_scenario_id"],
            active_scenario_description=row["active_scenario_description"] or "",
            user_prompt=row["user_prompt"],
            system_prompt=row["system_prompt"] if "system_prompt" in row.keys() else None,
            synopsis_beat=row["synopsis_beat"] if "synopsis_beat" in row.keys() else None,
            beat_type=BeatType(raw_type) if raw_type else None,
            created_at=created_at,
        )
