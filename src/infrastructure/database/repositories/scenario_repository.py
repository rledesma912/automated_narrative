"""SQL Scenario Repository."""

from uuid import UUID

from src.domain.models import Scenario


class SQLScenarioRepository:
    """SQLite repository para escenarios cronológicos."""

    async def save_batch(self, scenarios: list[Scenario], story_id: UUID) -> list[Scenario]:
        """Persiste la lista completa de escenarios de una historia."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        for scenario in scenarios:
            await conn.execute(
                """INSERT OR REPLACE INTO scenario (id, story_id, order_index, name)
                VALUES (?, ?, ?, ?)""",
                (
                    str(scenario.id),
                    str(story_id),
                    scenario.order_index,
                    scenario.name,
                ),
            )
        await conn.commit()
        await conn.close()
        return scenarios

    async def get_by_story(self, story_id: UUID) -> list[Scenario]:
        """Retorna los escenarios de una historia ordenados cronológicamente."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        cursor = await conn.execute(
            "SELECT * FROM scenario WHERE story_id = ? ORDER BY order_index",
            (str(story_id),),
        )
        rows = await cursor.fetchall()
        await conn.close()
        return [
            Scenario(
                id=UUID(row["id"]),
                story_id=UUID(row["story_id"]),
                order_index=row["order_index"],
                name=row["name"],
            )
            for row in rows
        ]

    async def delete_by_story(self, story_id: UUID) -> None:
        """Elimina todos los escenarios de una historia."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        await conn.execute("DELETE FROM scenario WHERE story_id = ?", (str(story_id),))
        await conn.commit()
        await conn.close()
