"""SQL MacroBeat Repository."""

from uuid import UUID

from src.domain.models import BeatType, MacroBeat
from src.infrastructure.database.connection import get_connection

# Alias público para código existente que importa Beat
Beat = MacroBeat


class SQLBeatRepository:
    """SQLite repository para macro_beats con normalización de reglas (Spec-041)."""

    async def save(self, beat: MacroBeat, story_id: UUID) -> MacroBeat:
        """Persiste un macro_beat y sus relaciones de reglas."""
        conn = await get_connection()

        # 1. Insertar/Reemplazar el beat (sin active_rules que ahora es una tabla de unión)
        cursor = await conn.execute(
            """INSERT OR REPLACE INTO macro_beat
            (story_id, number, summary, content, status,
             active_scenario_id, active_scenario_description,
             narrative_context, type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(story_id),
                beat.number,
                beat.summary,
                beat.content,
                beat.status,
                beat.active_scenario_id,
                beat.active_scenario_description,
                beat.narrative_context,
                beat.beat_type.value if beat.beat_type else None,
                beat.created_at.isoformat(),
            ),
        )

        # Obtener el ID del beat (necesario para la tabla de unión)
        # En SQLite, INSERT OR REPLACE puede cambiar el ROWID.
        # Buscamos por story_id y number para ser seguros.
        cursor = await conn.execute(
            "SELECT id FROM macro_beat WHERE story_id = ? AND number = ?",
            (str(story_id), beat.number),
        )
        row = await cursor.fetchone()
        beat_db_id = row["id"]

        # 2. Persistir relaciones con reglas
        await conn.execute("DELETE FROM macro_beat_rule WHERE macro_beat_id = ?", (beat_db_id,))

        if beat.active_rules:
            for rule_content in beat.active_rules:
                # Buscar el ID de la regla por su contenido y story_id
                cursor_rule = await conn.execute(
                    "SELECT id FROM rule WHERE story_id = ? AND content = ?",
                    (str(story_id), rule_content),
                )
                rule_row = await cursor_rule.fetchone()
                if rule_row:
                    await conn.execute(
                        "INSERT INTO macro_beat_rule (macro_beat_id, rule_id) VALUES (?, ?)",
                        (beat_db_id, rule_row["id"]),
                    )

        await conn.commit()
        await conn.close()
        return beat

    async def get_by_story(self, story_id: UUID) -> list[MacroBeat]:
        """Retorna todos los macro_beats de una historia con sus reglas cargadas."""
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM macro_beat WHERE story_id = ? ORDER BY number",
            (str(story_id),),
        )
        rows = await cursor.fetchall()

        beats = []
        for row in rows:
            beat = await self._row_to_beat_with_rules(row, conn)
            beats.append(beat)

        await conn.close()
        return beats

    async def get_by_number(self, story_id: UUID, number: int) -> MacroBeat | None:
        """Retorna un macro_beat específico con sus reglas cargadas."""
        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM macro_beat WHERE story_id = ? AND number = ?",
            (str(story_id), number),
        )
        row = await cursor.fetchone()

        if not row:
            await conn.close()
            return None

        beat = await self._row_to_beat_with_rules(row, conn)
        await conn.close()
        return beat

    async def update(self, beat: MacroBeat, story_id: UUID) -> MacroBeat:
        """Actualiza un macro_beat existente."""
        return await self.save(beat, story_id)

    async def _row_to_beat_with_rules(self, row, conn) -> MacroBeat:
        """Helper para convertir row a MacroBeat cargando reglas desde la tabla de unión."""
        beat_db_id = row["id"]

        # Cargar contenidos de reglas via JOIN
        cursor = await conn.execute(
            """SELECT r.content
               FROM rule r
               JOIN macro_beat_rule mbr ON r.id = mbr.rule_id
               WHERE mbr.macro_beat_id = ?""",
            (beat_db_id,),
        )
        rule_rows = await cursor.fetchall()
        active_rules = [r["content"] for r in rule_rows]

        from datetime import datetime

        raw_type = row["type"] if "type" in row.keys() else None
        raw_created_at = row["created_at"] if "created_at" in row.keys() else None
        created_at = datetime.fromisoformat(raw_created_at) if raw_created_at else None
        return MacroBeat(
            number=row["number"],
            summary=row["summary"],
            content=row["content"] or "",
            status=row["status"],
            active_scenario_id=row["active_scenario_id"],
            active_rules=active_rules,
            active_scenario_description=row["active_scenario_description"] or "",
            narrative_context=row["narrative_context"],
            beat_type=BeatType(raw_type) if raw_type else None,
            created_at=created_at,
        )
