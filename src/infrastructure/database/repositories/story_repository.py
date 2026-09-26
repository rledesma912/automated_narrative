"""SQL Story Repository."""

import json
import uuid
from uuid import UUID

from src.domain.models import (
    ActOutline,
    CharacterKind,
    Direction,
    Entity,
    NarrativeJournal,
    RuleType,
    Story,
    StoryStatus,
    TypedRule,
    WorkshopItem,
)
from src.infrastructure.database.connection import connection, get_connection


class SQLStoryRepository:
    """SQLite implementation of StoryRepository."""

    async def save(self, story: Story) -> Story:
        """Save a story (alta de una historia: creación o import-yaml).

        `INSERT OR REPLACE` sobre `story` borra en cascada todo lo que cuelga de
        ella (actos, journal, taller, escaleta, relatos, jobs): no usar para editar
        una historia existente; para eso está `update_inputs()`.
        """
        conn = await get_connection()
        # try/finally: una conexión sin cerrar (p. ej. la FK del catálogo rechaza el
        # INSERT) deja vivo el hilo de aiosqlite.
        try:
            await conn.execute(
                """INSERT OR REPLACE INTO story
                (id, title, protagonista, relator, sinopsis, genero, subgenero, tono,
                 narrator_config, direction, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(story.id),
                    story.title,
                    story.protagonista,
                    story.relator,
                    story.sinopsis,
                    story.genero or None,  # NULL: la FK del catálogo rechaza ""
                    story.subgenero or None,
                    story.tono,
                    json.dumps(story.narrator_config) if story.narrator_config else None,
                    _direction_json(story.direction),
                    story.status.value,
                    story.created_at.isoformat(),
                ),
            )

            await self._write_inputs(conn, story)
            for item in story.workshop:
                await self._upsert_workshop_item(conn, str(story.id), item)
            await self._replace_outline(conn, str(story.id), story.outline)

            # Persistir beats en la tabla macro_beat (borrar y re-insertar)
            # Spec-190 T7.1: pre-crear 5 filas macro_beat al guardar la historia
            await conn.execute("DELETE FROM macro_beat WHERE story_id = ?", (str(story.id),))
            if story.beats:
                for b in story.beats:
                    await conn.execute(
                        """INSERT INTO macro_beat
                        (story_id, number, summary, synopsis_beat, type, status)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            str(story.id),
                            b.number,
                            b.summary,
                            b.synopsis_beat or "",
                            b.beat_type.value if b.beat_type else None,
                            b.status.value,
                        ),
                    )

            await conn.commit()
        finally:
            await conn.close()

        return story

    async def get_by_id(self, story_id: UUID) -> Story | None:
        """Get story by ID."""
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM story WHERE id = ?",
                (str(story_id),),
            )

            row = await cursor.fetchone()

            if not row:
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
                    description=(s["description"] if "description" in s.keys() else "") or "",
                )
                for s in scenario_rows
            ]

            personajes = await self._load_personajes(conn, str(story_id))
            entities = await self._load_entities(conn, str(story_id))
            workshop = await self._load_workshop(conn, str(story_id))
            outline = await self._load_outline(conn, str(story_id))

            beats = await self._load_beats(conn, str(story_id))

        story = self._row_to_story(row)
        story.reglas = reglas
        story.typed_rules = typed_rules
        story.scenarios = scenarios
        story.entities = entities
        story.personajes_full = personajes
        story.workshop = workshop
        story.outline = outline
        story.beats = beats
        return story

    async def get_by_string_id(self, story_id: str) -> Story | None:
        """Get story by string ID (e.g., 'el_monte_prohibido_1744742400')."""
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM story WHERE id = ?",
                (story_id,),
            )

            row = await cursor.fetchone()

            if not row:
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
                    description=(s["description"] if "description" in s.keys() else "") or "",
                )
                for s in scenario_rows
            ]

            personajes = await self._load_personajes(conn, story_id)
            entities = await self._load_entities(conn, story_id)
            workshop = await self._load_workshop(conn, story_id)
            outline = await self._load_outline(conn, story_id)

        story = self._row_to_story(row)
        story.workshop = workshop
        story.outline = outline
        story.reglas = reglas
        story.typed_rules = typed_rules
        story.scenarios = scenarios
        story.entities = entities
        story.personajes_full = personajes
        return story

    async def update_inputs(self, story: Story) -> Story:
        """Actualiza solo los datos de entrada de una historia (Spec-440 §8).

        A diferencia de `save()`, no toca lo generado: nada de `INSERT OR REPLACE`
        sobre `story` (con FKs en cascada borraría actos, journal, anclas, relatos
        y jobs) ni reescritura de `macro_beat`. Tampoco cambia `status`.

        Tampoco toca la dirección, el taller ni la escaleta (Spec-530): tienen sus
        propios métodos, así una edición que no los manda no los borra.
        """
        conn = await get_connection()
        try:
            await conn.execute(
                """UPDATE story SET title = ?, protagonista = ?, relator = ?, sinopsis = ?,
                   genero = ?, subgenero = ?, tono = ?, narrator_config = ?
                   WHERE id = ?""",
                (
                    story.title,
                    story.protagonista,
                    story.relator,
                    story.sinopsis,
                    story.genero or None,  # NULL: la FK del catálogo rechaza ""
                    story.subgenero or None,
                    story.tono,
                    json.dumps(story.narrator_config) if story.narrator_config else None,
                    str(story.id),
                ),
            )
            await self._write_inputs(conn, story)
            await conn.commit()
        finally:
            await conn.close()
        return story

    async def _write_inputs(self, conn, story: Story) -> None:
        """Personajes, reglas, escenarios y entidades: borrar y re-insertar (datos de entrada)."""
        # Persistir personajes en la tabla character (borrar y re-insertar).
        # El id de DB es un UUID fresco, igual que en rule/scenario; el id
        # corto del YAML (P1, P2…) es story-scoped y se conserva solo en memoria.
        await conn.execute("DELETE FROM character WHERE story_id = ?", (str(story.id),))
        for idx, p in enumerate(story.personajes_full or [], start=1):
            await conn.execute(
                "INSERT INTO character (id, story_id, name, role, traits, kind, relation, "
                "order_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    str(story.id),
                    p.get("name", ""),
                    p.get("role", ""),
                    json.dumps(list(p.get("traits") or [])),
                    CharacterKind(p.get("kind") or CharacterKind.PERSONA).value,
                    p.get("relation", "") or "",
                    idx,
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
                    "INSERT INTO scenario (id, story_id, order_index, name, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (str(s.id), str(story.id), s.order_index, s.name, s.description or ""),
                )

        # Spec-450: entidades (borrar y re-insertar). `entity_journal` no depende de
        # estos ids, así que editar la historia no pierde el estado del journal.
        await conn.execute("DELETE FROM entity WHERE story_id = ?", (str(story.id),))
        for e in story.entities:
            await conn.execute(
                "INSERT INTO entity (id, story_id, order_index, name, nature_id, description, "
                "manifestations, limits, reveal_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(e.id),
                    str(story.id),
                    e.order_index,
                    e.name,
                    e.nature_id,
                    e.description,
                    e.manifestations,
                    e.limits,
                    e.reveal_level.value,
                ),
            )

    async def _load_entities(self, conn, story_id: str) -> list[Entity]:
        cursor = await conn.execute(
            "SELECT e.*, n.label AS nature_label FROM entity e "
            "LEFT JOIN entity_nature n ON n.id = e.nature_id "
            "WHERE e.story_id = ? ORDER BY e.order_index",
            (story_id,),
        )
        return [
            Entity(
                id=UUID(r["id"]),
                story_id=UUID(r["story_id"]),
                order_index=r["order_index"],
                name=r["name"] or "",
                nature_id=r["nature_id"],
                description=r["description"] or "",
                manifestations=r["manifestations"] or "",
                limits=r["limits"] or "",
                reveal_level=r["reveal_level"],
                nature_label=r["nature_label"] or "",
            )
            for r in await cursor.fetchall()
        ]

    async def update(self, story: Story) -> Story:
        """Update a story."""
        return await self.save(story)

    async def update_status(self, story_id, status: str) -> None:
        """Actualiza solo el campo status de una historia."""
        async with connection() as conn:
            await conn.execute(
                "UPDATE story SET status = ? WHERE id = ?",
                (status, str(story_id)),
            )
            await conn.commit()

    async def list_all(self) -> list[Story]:
        """List all stories."""
        async with connection() as conn:
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

                personajes = await self._load_personajes(conn, story_id)

                story = self._row_to_story(row)
                story.reglas = reglas
                story.typed_rules = self._rows_to_typed_rules(rule_rows, story_id)
                story.scenarios = scenarios
                story.entities = await self._load_entities(conn, story_id)
                story.personajes_full = personajes
                stories.append(story)

        return stories

    async def save_journal(
        self, story_id: UUID, journal: NarrativeJournal, beat_number: int
    ) -> None:
        """Save the narrative journal for a specific beat (Spec-222)."""
        async with connection() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO narrative_journal
                (story_id, beat_number, last_events, unresolved_mysteries,
                 physical_emotional_state, used_motifs)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(story_id),
                    beat_number,
                    journal.last_events,
                    journal.unresolved_mysteries,
                    journal.physical_emotional_state,
                    json.dumps(journal.used_motifs, ensure_ascii=False),
                ),
            )
            # Spec-450: el estado de las entidades vive en su propia tabla.
            if journal.entity_state:
                await conn.execute(
                    "INSERT OR REPLACE INTO entity_journal (id, story_id, beat_number, entity_state) "
                    "VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), str(story_id), beat_number, journal.entity_state),
                )

            await conn.commit()

    async def get_journal(
        self, story_id: UUID, beat_number: int | None = None
    ) -> NarrativeJournal | None:
        """Get the narrative journal for a story.

        Args:
            story_id: UUID de la historia.
            beat_number: Si se especifica, retorna el journal de ese beat.
                        Si es None, retorna el journal del último beat completado.
        """
        async with connection() as conn:
            select = (
                "SELECT j.*, ej.entity_state FROM narrative_journal j "
                "LEFT JOIN entity_journal ej "
                "ON ej.story_id = j.story_id AND ej.beat_number = j.beat_number "
                "WHERE j.story_id = ?"
            )
            if beat_number is not None:
                cursor = await conn.execute(
                    f"{select} AND j.beat_number = ?", (str(story_id), beat_number)
                )
            else:
                cursor = await conn.execute(
                    f"{select} ORDER BY j.beat_number DESC LIMIT 1", (str(story_id),)
                )

            row = await cursor.fetchone()

        if not row:
            return None

        return NarrativeJournal(
            last_events=row["last_events"],
            unresolved_mysteries=row["unresolved_mysteries"],
            physical_emotional_state=row["physical_emotional_state"],
            entity_state=row["entity_state"] or "",
            used_motifs=json.loads(row["used_motifs"] or "[]"),
        )

    async def clear_story_artifacts(self, story_id) -> None:
        """Limpia artefactos generados (beats, journal, anchors) para reinicio limpio (Spec-212)."""
        conn = await get_connection()
        sid = str(story_id)
        try:
            await conn.execute("DELETE FROM narrative_journal WHERE story_id = ?", (sid,))
            await conn.execute("DELETE FROM entity_journal WHERE story_id = ?", (sid,))
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

        async with connection() as conn:
            cursor = await conn.execute(
                "UPDATE story SET status = ? WHERE status = ?",
                (StoryStatus.FAILED.value, StoryStatus.PROCESSING.value),
            )
            count = cursor.rowcount
            await conn.commit()
        if count > 0:
            logging.getLogger(__name__).warning(
                "Recuperadas %d historias en estado inconsistente tras reinicio", count
            )
        return count

    async def delete(self, story_id: UUID) -> None:
        """Hard delete: borra la historia y todas sus tablas hija."""
        async with connection() as conn:
            sid = str(story_id)
            await conn.execute(
                "DELETE FROM generated_narrative WHERE story_template_id = ?", (sid,)
            )
            await conn.execute("DELETE FROM narrative_journal WHERE story_id = ?", (sid,))
            await conn.execute("DELETE FROM macro_beat WHERE story_id = ?", (sid,))
            await conn.execute("DELETE FROM rule WHERE story_id = ?", (sid,))
            await conn.execute("DELETE FROM scenario WHERE story_id = ?", (sid,))
            await conn.execute("DELETE FROM character WHERE story_id = ?", (sid,))
            await conn.execute("DELETE FROM story WHERE id = ?", (sid,))
            await conn.commit()

    async def update_direction(self, story_id: UUID, direction: Direction | None) -> None:
        """Guarda la dirección de una historia (vista Dirección)."""
        async with connection() as conn:
            await conn.execute(
                "UPDATE story SET direction = ? WHERE id = ?",
                (_direction_json(direction), str(story_id)),
            )
            await conn.commit()

    async def get_workshop(self, story_id: UUID) -> list[WorkshopItem]:
        async with connection() as conn:
            return await self._load_workshop(conn, str(story_id))

    async def save_workshop_items(self, story_id: UUID, items: list[WorkshopItem]) -> None:
        """Crea o actualiza criterios del taller (uno por nivel y criterio)."""
        async with connection() as conn:
            for item in items:
                await self._upsert_workshop_item(conn, str(story_id), item)
            await conn.commit()

    async def get_outline(self, story_id: UUID) -> list[ActOutline]:
        async with connection() as conn:
            return await self._load_outline(conn, str(story_id))

    async def save_outline(self, story_id: UUID, acts: list[ActOutline]) -> None:
        """Reemplaza la escaleta completa (la arma el Planificador)."""
        async with connection() as conn:
            await self._replace_outline(conn, str(story_id), acts)
            await conn.commit()

    async def save_act(self, story_id: UUID, act: ActOutline) -> None:
        """Crea o actualiza un acto de la escaleta (edición del usuario)."""
        async with connection() as conn:
            await self._upsert_act(conn, str(story_id), act)
            await conn.commit()

    async def _upsert_workshop_item(self, conn, story_id: str, item: WorkshopItem) -> None:
        await conn.execute(
            "INSERT INTO story_workshop (story_id, level, criterion, status, question, "
            "options, answer, round, question_round, asked) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (story_id, level, criterion) DO UPDATE SET status = excluded.status, "
            "question = excluded.question, options = excluded.options, "
            "answer = excluded.answer, round = excluded.round, "
            "question_round = excluded.question_round, asked = excluded.asked",
            (
                story_id,
                item.level.value,
                item.criterion,
                item.status.value,
                item.question,
                json.dumps(item.options, ensure_ascii=False),
                item.answer,
                item.round,
                item.question_round,
                json.dumps(item.asked, ensure_ascii=False),
            ),
        )

    async def _load_workshop(self, conn, story_id: str) -> list[WorkshopItem]:
        cursor = await conn.execute(
            "SELECT * FROM story_workshop WHERE story_id = ? ORDER BY level, id", (story_id,)
        )
        return [
            WorkshopItem(
                level=r["level"],
                criterion=r["criterion"],
                status=r["status"],
                question=r["question"] or "",
                options=json.loads(r["options"] or "[]"),
                answer=r["answer"] or "",
                round=r["round"],
                question_round=r["question_round"],
                asked=json.loads(r["asked"] or "[]"),
            )
            for r in await cursor.fetchall()
        ]

    async def _replace_outline(self, conn, story_id: str, acts: list[ActOutline]) -> None:
        await conn.execute("DELETE FROM act_outline WHERE story_id = ?", (story_id,))
        for act in acts:
            await self._upsert_act(conn, story_id, act)

    async def _upsert_act(self, conn, story_id: str, act: ActOutline) -> None:
        def js(value: list[str]) -> str:
            return json.dumps(value, ensure_ascii=False)

        await conn.execute(
            "INSERT INTO act_outline (story_id, number, goal, events, change_from, change_to, "
            "scenario, on_stage, held_back, seeds, payoffs, decisions, warnings, needs_review) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (story_id, number) DO UPDATE SET goal = excluded.goal, "
            "events = excluded.events, change_from = excluded.change_from, "
            "change_to = excluded.change_to, scenario = excluded.scenario, "
            "on_stage = excluded.on_stage, held_back = excluded.held_back, "
            "seeds = excluded.seeds, payoffs = excluded.payoffs, "
            "decisions = excluded.decisions, warnings = excluded.warnings, "
            "needs_review = excluded.needs_review",
            (
                story_id,
                act.number,
                act.goal,
                js(act.events),
                act.change_from,
                act.change_to,
                act.scenario,
                js(act.on_stage),
                act.held_back,
                js(act.seeds),
                js(act.payoffs),
                js(act.decisions),
                js(act.warnings),
                int(act.needs_review),
            ),
        )

    async def _load_outline(self, conn, story_id: str) -> list[ActOutline]:
        cursor = await conn.execute(
            "SELECT * FROM act_outline WHERE story_id = ? ORDER BY number", (story_id,)
        )
        lists = ("events", "on_stage", "seeds", "payoffs", "decisions", "warnings")
        return [
            ActOutline(
                number=r["number"],
                goal=r["goal"] or "",
                change_from=r["change_from"] or "",
                change_to=r["change_to"] or "",
                scenario=r["scenario"] or "",
                held_back=r["held_back"] or "",
                needs_review=bool(r["needs_review"]),
                **{k: json.loads(r[k] or "[]") for k in lists},
            )
            for r in await cursor.fetchall()
        ]

    async def _load_personajes(self, conn, story_id: str) -> list[dict]:
        """Carga los personajes de una historia desde la tabla character.

        Reconstruye el id corto story-scoped (P1, P2…) desde order_index, ya
        que no se persiste: la tabla guarda un UUID como PK (convención de
        rule/scenario). El resultado alimenta `Story.personajes_full`.
        """
        cursor = await conn.execute(
            "SELECT name, role, traits, kind, relation, order_index FROM character "
            "WHERE story_id = ? ORDER BY order_index",
            (story_id,),
        )
        rows = await cursor.fetchall()
        personajes = []
        for c in rows:
            raw_traits = c["traits"]
            personajes.append(
                {
                    "id": f"P{c['order_index']}",
                    "name": c["name"],
                    "role": c["role"] or "",
                    "traits": json.loads(raw_traits) if raw_traits else [],
                    "kind": c["kind"] or CharacterKind.PERSONA.value,
                    "relation": c["relation"] or "",
                }
            )
        return personajes

    async def _load_beats(self, conn, story_id: str) -> list:
        """Carga los beats de una historia desde la tabla macro_beat."""
        from src.domain.models import BeatStatus, MacroBeat

        cursor = await conn.execute(
            "SELECT number, summary, synopsis_beat, type, status, "
            "generated_act, active_scenario_id FROM macro_beat "
            "WHERE story_id = ? ORDER BY number",
            (story_id,),
        )
        rows = await cursor.fetchall()
        beats = []
        for b in rows:
            raw_type = b["type"] if "type" in b.keys() else None
            beat_type = None
            if raw_type:
                try:
                    from src.domain.models import BeatType

                    beat_type = BeatType(raw_type)
                except ValueError:
                    pass
            beats.append(
                MacroBeat(
                    number=b["number"],
                    summary=b["summary"] or "",
                    synopsis_beat=b["synopsis_beat"] if "synopsis_beat" in b.keys() else None,
                    beat_type=beat_type,
                    status=BeatStatus(b["status"]) if b["status"] else BeatStatus.PENDING,
                    generated_act=b["generated_act"] or "",
                    active_scenario_id=b["active_scenario_id"]
                    if "active_scenario_id" in b.keys()
                    else None,
                )
            )
        return beats

    def _row_to_story(self, row) -> Story:
        """Convert row to Story."""
        from datetime import datetime

        keys = row.keys()
        raw_cfg = row["narrator_config"] if "narrator_config" in keys else None
        raw_direction = row["direction"] if "direction" in keys else None
        raw_created_at = row["created_at"] if "created_at" in keys else None
        created_at = datetime.fromisoformat(raw_created_at) if raw_created_at else None
        return Story(
            id=UUID(row["id"]),
            title=row["title"],
            protagonista=row["protagonista"],
            relator=row["relator"],
            sinopsis=row["sinopsis"],
            genero=(row["genero"] if "genero" in keys else "") or "",
            subgenero=(row["subgenero"] if "subgenero" in keys else "") or "",
            tono=(row["tono"] if "tono" in keys else "") or "",
            narrator_config=json.loads(raw_cfg) if raw_cfg else None,
            direction=Direction.model_validate_json(raw_direction) if raw_direction else None,
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
            rule_type = RuleType.from_raw(raw_type)
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


def _direction_json(direction: Direction | None) -> str | None:
    return direction.model_dump_json() if direction else None
