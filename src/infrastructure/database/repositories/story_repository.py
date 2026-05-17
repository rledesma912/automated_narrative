"""SQL Story Repository."""

import json
import uuid
from uuid import UUID

from src.domain.models import NarrativeJournal, RuleType, Story, StoryStatus, TypedRule
from src.infrastructure.database.connection import get_connection
from src.utils.timezone import now_argentina


class SQLStoryRepository:
    """SQLite implementation of StoryRepository."""

    async def save(self, story: Story) -> Story:
        """Save a story."""
        conn = await get_connection()

        await conn.execute(
            """INSERT OR REPLACE INTO story
            (id, title, protagonista, relator, sinopsis, atmosfera,
             storyteller_config, personajes, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(story.id),
                story.title,
                story.protagonista,
                story.relator,
                story.sinopsis,
                story.atmosfera,
                json.dumps(story.storyteller_config) if story.storyteller_config else None,
                json.dumps(story.personajes_full),
                story.status.value,
                story.created_at.isoformat(),
            ),
        )

        # Persistir reglas en la tabla rule (borrar y re-insertar)
        # Siempre se genera un UUID fresco como PK de DB para evitar colisiones entre historias.
        # El r.id lógico ("R1", "R2"…) vive solo en TypedRule, no en la tabla.
        await conn.execute("DELETE FROM rule WHERE story_id = ?", (str(story.id),))
        if story.typed_rules:
            for r in story.typed_rules:
                db_rule_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO rule (id, story_id, content, type, intensity, applies_to_beat) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        db_rule_id,
                        str(story.id),
                        r.content,
                        r.type.value if r.type else None,
                        r.intensity,
                        r.applies_to_beat,
                    ),
                )
        elif story.reglas:
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
            "SELECT id, content, type, intensity, applies_to_beat FROM rule WHERE story_id = ?",
            (str(story_id),),
        )
        rule_rows = await cursor_rules.fetchall()
        reglas = [r["content"] for r in rule_rows]
        typed_rules = self._rows_to_typed_rules(rule_rows, str(story_id))

        # Cargar escenarios
        from src.domain.models import Scenario

        cursor_scenarios = await conn.execute(
            "SELECT * FROM scenario WHERE story_id = ? ORDER BY order_index",
            (str(story_id),),
        )
        scenario_rows = await cursor_scenarios.fetchall()
        scenarios = [
            Scenario(
                id=UUID(s["id"]),
                story_id=UUID(s["story_id"]),
                order_index=s["order_index"],
                name=s["name"],
            )
            for s in scenario_rows
        ]

        await conn.close()

        story = self._row_to_story(row)
        story.reglas = reglas
        story.typed_rules = typed_rules
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
            "SELECT id, content, type, intensity, applies_to_beat FROM rule WHERE story_id = ?",
            (story_id,),
        )
        rule_rows = await cursor_rules.fetchall()
        reglas = [r["content"] for r in rule_rows]
        typed_rules = self._rows_to_typed_rules(rule_rows, story_id)

        # Cargar escenarios
        from src.domain.models import Scenario

        cursor_scenarios = await conn.execute(
            "SELECT * FROM scenario WHERE story_id = ? ORDER BY order_index",
            (story_id,),
        )
        scenario_rows = await cursor_scenarios.fetchall()
        scenarios = [
            Scenario(
                id=UUID(s["id"]),
                story_id=UUID(s["story_id"]),
                order_index=s["order_index"],
                name=s["name"],
            )
            for s in scenario_rows
        ]

        await conn.close()

        story = self._row_to_story(row)
        story.reglas = reglas
        story.typed_rules = typed_rules
        story.scenarios = scenarios
        return story

    async def update(self, story: Story) -> Story:
        """Update a story."""
        return await self.save(story)

    async def update_status(self, story_id, status: str) -> None:
        """Actualiza solo el campo status de una historia."""
        from src.infrastructure.database.connection import get_connection

        conn = await get_connection()
        await conn.execute(
            "UPDATE story SET status = ? WHERE id = ?",
            (status, str(story_id)),
        )
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
                "SELECT id, content, type, intensity, applies_to_beat FROM rule WHERE story_id = ?",
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
                Scenario(
                    id=UUID(s["id"]),
                    story_id=UUID(s["story_id"]),
                    order_index=s["order_index"],
                    name=s["name"],
                )
                for s in scenario_rows
            ]

            story = self._row_to_story(row)
            story.reglas = reglas
            story.typed_rules = self._rows_to_typed_rules(rule_rows, story_id)
            story.scenarios = scenarios
            stories.append(story)

        await conn.close()
        return stories

    async def save_journal(
        self, story_id: UUID, journal: NarrativeJournal, beat_number: int
    ) -> None:
        """Save the narrative journal for a specific beat (Spec-222)."""
        conn = await get_connection()

        await conn.execute(
            """INSERT OR REPLACE INTO narrative_journal
            (story_id, beat_number, last_events, unresolved_mysteries, physical_emotional_state)
            VALUES (?, ?, ?, ?, ?)""",
            (
                str(story_id),
                beat_number,
                journal.last_events,
                journal.unresolved_mysteries,
                journal.physical_emotional_state,
            ),
        )

        await conn.commit()
        await conn.close()

    async def get_journal(
        self, story_id: UUID, beat_number: int | None = None
    ) -> NarrativeJournal | None:
        """Get the narrative journal for a story.

        Args:
            story_id: UUID de la historia.
            beat_number: Si se especifica, retorna el journal de ese beat.
                        Si es None, retorna el journal del último beat completado.
        """
        conn = await get_connection()

        if beat_number is not None:
            cursor = await conn.execute(
                "SELECT * FROM narrative_journal WHERE story_id = ? AND beat_number = ?",
                (str(story_id), beat_number),
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM narrative_journal WHERE story_id = ? ORDER BY beat_number DESC LIMIT 1",
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

    async def clear_story_artifacts(self, story_id) -> None:
        """Limpia artefactos generados (beats, journal, anchors) para reinicio limpio (Spec-212)."""
        conn = await get_connection()
        sid = str(story_id)
        try:
            await conn.execute("DELETE FROM narrative_journal WHERE story_id = ?", (sid,))
            await conn.execute("DELETE FROM narrative_anchors WHERE story_id = ?", (sid,))
            await conn.execute("DELETE FROM macro_beat WHERE story_id = ?", (sid,))
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    async def recover_processing_stories(self) -> int:
        """Transición masiva processing → failed tras reinicio del servidor (Spec-214 B1)."""
        import logging

        conn = await get_connection()
        cursor = await conn.execute(
            "UPDATE story SET status = ? WHERE status = ?",
            (StoryStatus.FAILED.value, StoryStatus.PROCESSING.value),
        )
        count = cursor.rowcount
        await conn.commit()
        await conn.close()
        if count > 0:
            logging.getLogger(__name__).warning(
                "Recuperadas %d historias en estado inconsistente tras reinicio", count
            )
        return count

    async def delete(self, story_id: UUID) -> None:
        """Hard delete: borra la historia y todas sus tablas hija."""
        conn = await get_connection()
        sid = str(story_id)
        await conn.execute("DELETE FROM generated_narrative WHERE story_template_id = ?", (sid,))
        await conn.execute("DELETE FROM narrative_journal WHERE story_id = ?", (sid,))
        await conn.execute("DELETE FROM narrative_anchors WHERE story_id = ?", (sid,))
        await conn.execute("DELETE FROM macro_beat WHERE story_id = ?", (sid,))
        await conn.execute("DELETE FROM rule WHERE story_id = ?", (sid,))
        await conn.execute("DELETE FROM scenario WHERE story_id = ?", (sid,))
        await conn.execute("DELETE FROM story WHERE id = ?", (sid,))
        await conn.commit()
        await conn.close()

    async def save_narrative_anchors(self, story_id, anchors) -> None:
        """Persiste los 5 anclajes de resonancia aristotélica (Spec-081)."""
        conn = await get_connection()
        # Nota: Usamos una subquery para el ID o generamos uno si es nuevo,
        # pero para simplificar seguiremos el patrón de INSERT OR REPLACE por story_id
        # si la tabla tiene story_id como UNIQUE o PK. En SQLite actual es story_id NOT NULL.
        # Vamos a asegurar que id sea único.
        import uuid

        # Primero buscamos si ya existe un ID para este story_id
        cursor = await conn.execute(
            "SELECT id FROM narrative_anchors WHERE story_id = ?", (str(story_id),)
        )
        row = await cursor.fetchone()
        anchor_id = row[0] if row else str(uuid.uuid4())

        await conn.execute(
            """INSERT OR REPLACE INTO narrative_anchors
            (id, story_id, resonance_hamartia, resonance_hybris, resonance_anagnorisis,
             resonance_peripeteia, resonance_residual, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                anchor_id,
                str(story_id),
                anchors.resonance_hamartia,
                anchors.resonance_hybris,
                anchors.resonance_anagnorisis,
                anchors.resonance_peripeteia,
                anchors.resonance_residual,
                now_argentina().isoformat(),
            ),
        )
        await conn.commit()
        await conn.close()

    def _row_to_story(self, row) -> Story:
        """Convert row to Story."""
        from datetime import datetime

        keys = row.keys()
        raw_cfg = row["storyteller_config"] if "storyteller_config" in keys else None
        raw_personajes = row["personajes"] if "personajes" in keys else None
        raw_created_at = row["created_at"] if "created_at" in keys else None
        created_at = datetime.fromisoformat(raw_created_at) if raw_created_at else None
        return Story(
            id=UUID(row["id"]),
            title=row["title"],
            protagonista=row["protagonista"],
            relator=row["relator"],
            sinopsis=row["sinopsis"],
            atmosfera=row["atmosfera"],
            storyteller_config=json.loads(raw_cfg) if raw_cfg else None,
            personajes_full=json.loads(raw_personajes) if raw_personajes else [],
            status=StoryStatus(row["status"])
            if row["status"] in [s.value for s in StoryStatus]
            else StoryStatus.DRAFT,
            created_at=created_at,
        )

    def _rows_to_typed_rules(self, rule_rows, story_id: str) -> list[TypedRule]:
        """Convierte filas de rule en TypedRule, tolerando columnas faltantes."""
        result = []
        for r in rule_rows:
            keys = r.keys()
            raw_type = r["type"] if "type" in keys else None
            raw_intensity = r["intensity"] if "intensity" in keys else None
            raw_applies = r["applies_to_beat"] if "applies_to_beat" in keys else None
            try:
                rule_type = RuleType(raw_type) if raw_type else None
            except ValueError:
                rule_type = None
            result.append(
                TypedRule(
                    id=r["id"],
                    story_id=UUID(story_id) if len(story_id) == 36 else story_id,  # type: ignore[arg-type]
                    content=r["content"],
                    type=rule_type,
                    intensity=raw_intensity,
                    applies_to_beat=raw_applies,
                )
            )
        return result
