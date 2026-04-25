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
            (id, title, protagonista, relator, sinopsis, atmosfera, narrative_brief, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(story.id),
                story.title,
                story.protagonista,
                story.relator,
                story.sinopsis,
                story.atmosfera,
                story.narrative_brief,
                story.status.value,
                story.created_at.isoformat(),
            ),
        )

        # Persistir reglas en la tabla rule (borrar y re-insertar)
        await conn.execute("DELETE FROM rule WHERE story_id = ?", (str(story.id),))
        if story.reglas:
            import uuid
            for r in story.reglas:
                rule_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO rule (id, story_id, content) VALUES (?, ?, ?)",
                    (rule_id, str(story.id), r),
                )

        # Persistir escenarios en la tabla scenario (borrar y re-insertar)
        await conn.execute("DELETE FROM scenario WHERE story_id = ?", (str(story.id),))
        if story.scenarios:
            for s in story.scenarios:
                await conn.execute(
                    "INSERT INTO scenario (id, story_id, order_index, name) VALUES (?, ?, ?, ?)",
                    (str(s.id), str(story.id), s.order_index, s.name),
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
        
        if not row:
            await conn.close()
            return None
        
        # Cargar reglas
        cursor_rules = await conn.execute(
            "SELECT content FROM rule WHERE story_id = ?",
            (str(story_id),),
        )
        rule_rows = await cursor_rules.fetchall()
        reglas = [r["content"] for r in rule_rows]

        # Cargar escenarios
        from src.domain.models import Scenario
        cursor_scenarios = await conn.execute(
            "SELECT * FROM scenario WHERE story_id = ? ORDER BY order_index",
            (str(story_id),),
        )
        scenario_rows = await cursor_scenarios.fetchall()
        scenarios = [
            Scenario(id=UUID(s["id"]), story_id=UUID(s["story_id"]), order_index=s["order_index"], name=s["name"])
            for s in scenario_rows
        ]
        
        await conn.close()

        story = self._row_to_story(row)
        story.reglas = reglas
        story.scenarios = scenarios
        return story

    async def get_by_string_id(self, story_id: str) -> Story | None:
        """Get story by string ID (e.g., 'el_monte_prohibido_1744742400')."""
        conn = await get_connection()

        cursor = await conn.execute(
            "SELECT * FROM story WHERE id = ?",
            (story_id,),
        )

        row = await cursor.fetchone()

        if not row:
            await conn.close()
            return None

        # Cargar reglas
        cursor_rules = await conn.execute(
            "SELECT content FROM rule WHERE story_id = ?",
            (story_id,),
        )
        rule_rows = await cursor_rules.fetchall()
        reglas = [r["content"] for r in rule_rows]

        # Cargar escenarios
        from src.domain.models import Scenario
        cursor_scenarios = await conn.execute(
            "SELECT * FROM scenario WHERE story_id = ? ORDER BY order_index",
            (story_id,),
        )
        scenario_rows = await cursor_scenarios.fetchall()
        scenarios = [
            Scenario(id=UUID(s["id"]), story_id=UUID(s["story_id"]), order_index=s["order_index"], name=s["name"])
            for s in scenario_rows
        ]

        await conn.close()

        story = self._row_to_story(row)
        story.reglas = reglas
        story.scenarios = scenarios
        return story

    async def update(self, story: Story) -> Story:
        """Update a story."""
        return await self.save(story)

    async def delete(self, story_id: UUID) -> None:
        """Delete a story."""
        conn = await get_connection()

        await conn.execute("DELETE FROM macro_beat_rule WHERE macro_beat_id IN (SELECT id FROM macro_beat WHERE story_id = ?)", (str(story_id),))
        await conn.execute("DELETE FROM macro_beat WHERE story_id = ?", (str(story_id),))
        await conn.execute("DELETE FROM rule WHERE story_id = ?", (str(story_id),))
        await conn.execute("DELETE FROM scenario WHERE story_id = ?", (str(story_id),))
        await conn.execute("DELETE FROM narrative_anchors WHERE story_id = ?", (str(story_id),))
        await conn.execute("DELETE FROM story WHERE id = ?", (str(story_id),))
        await conn.execute("DELETE FROM narrative_journal WHERE story_id = ?", (str(story_id),))

        await conn.commit()
        await conn.close()

    async def list_all(self) -> list[Story]:
        """List all stories."""
        conn = await get_connection()

        cursor = await conn.execute("SELECT * FROM story ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        
        stories = []
        for row in rows:
            story_id = row["id"]
            # Cargar reglas
            cursor_rules = await conn.execute(
                "SELECT content FROM rule WHERE story_id = ?",
                (story_id,),
            )
            rule_rows = await cursor_rules.fetchall()
            reglas = [r["content"] for r in rule_rows]

            # Cargar escenarios
            from src.domain.models import Scenario
            cursor_scenarios = await conn.execute(
                "SELECT * FROM scenario WHERE story_id = ? ORDER BY order_index",
                (story_id,),
            )
            scenario_rows = await cursor_scenarios.fetchall()
            scenarios = [
                Scenario(id=UUID(s["id"]), story_id=UUID(s["story_id"]), order_index=s["order_index"], name=s["name"])
                for s in scenario_rows
            ]
            
            story = self._row_to_story(row)
            story.reglas = reglas
            story.scenarios = scenarios
            stories.append(story)
            
        await conn.close()
        return stories

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
            sinopsis=row["sinopsis"],
            atmosfera=row["atmosfera"],
            narrative_brief=row["narrative_brief"] or "",
            status=StoryStatus(row["status"]),
        )
