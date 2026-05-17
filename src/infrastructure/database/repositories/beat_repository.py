"""SQL MacroBeat Repository."""

from datetime import datetime
from uuid import UUID

from src.domain.models import BeatType, MacroBeat
from src.infrastructure.database.connection import get_connection

# Alias público para código existente que importa Beat
Beat = MacroBeat


class SQLBeatRepository:
    """SQLite repository para macro_beats.

    Spec-190 §4.4: las reglas activas ya no se persisten per-beat (tabla
    macro_beat_rule eliminada); se derivan determinísticamente desde
    `rule.applies_to_beat` al generar.
    """

    async def save(self, beat: MacroBeat, story_id: UUID) -> MacroBeat:
        """Persiste un macro_beat."""
        conn = await get_connection()

        await conn.execute(
            """INSERT OR REPLACE INTO macro_beat
            (story_id, number, summary, synopsis_beat, generated_act, status,
             active_scenario_id, active_scenario_description,
             system_prompt, user_prompt, type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(story_id),
                beat.number,
                beat.summary,
                beat.synopsis_beat,
                beat.generated_act,
                beat.status,
                beat.active_scenario_id,
                beat.active_scenario_description,
                beat.system_prompt,
                beat.user_prompt,
                beat.beat_type.value if beat.beat_type else None,
                beat.created_at.isoformat(),
            ),
        )

        await conn.commit()
        await conn.close()
        return beat

    async def get_by_story(self, story_id: UUID) -> list[MacroBeat]:
        """Retorna todos los macro_beats de una historia."""
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM macro_beat WHERE story_id = ? ORDER BY number",
            (str(story_id),),
        )
        rows = await cursor.fetchall()
        await conn.close()
        return [self._row_to_beat(row) for row in rows]

    async def get_by_number(self, story_id: UUID, number: int) -> MacroBeat | None:
        """Retorna un macro_beat específico."""
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM macro_beat WHERE story_id = ? AND number = ?",
            (str(story_id), number),
        )
        row = await cursor.fetchone()
        await conn.close()

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
