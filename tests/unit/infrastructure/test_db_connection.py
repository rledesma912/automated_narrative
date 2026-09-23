"""Tests for database connection."""

import os
import tempfile

import pytest

from src.config import settings
from src.infrastructure.database.connection import get_connection, init_db


class TestDbConnection:
    """Tests for database connection."""

    @pytest.fixture
    def temp_db_path(self, monkeypatch):
        """Create temporary database path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{path}")
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    async def setup_db(self, temp_db_path):
        """Initialize database."""
        await init_db()

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, temp_db_path, setup_db):
        """Test that init_db creates required tables."""
        conn = await get_connection()

        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        table_names = [row["name"] for row in rows]
        await conn.close()

        assert "story" in table_names
        assert "macro_beat" in table_names
        assert "scenario" in table_names
        assert "narrative_anchors" in table_names
        assert "narrative_journal" in table_names

    @pytest.mark.asyncio
    async def test_get_connection_returns_connection(self, temp_db_path):
        """Test that get_connection returns a valid connection."""
        conn = await get_connection()

        assert conn is not None

        await conn.close()

    @pytest.mark.asyncio
    async def test_story_table_has_correct_columns(self, temp_db_path, setup_db):
        """Test that story table has all required columns."""
        conn = await get_connection()

        cursor = await conn.execute("PRAGMA table_info(story)")
        rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        await conn.close()

        required = {
            "id",
            "title",
            "protagonista",
            "relator",
            "sinopsis",
            "genero",
            "subgenero",
            "tono",
            "narrator_config",
            "status",
            "created_at",
        }
        assert required.issubset(columns), f"Missing: {required - columns}"

    @pytest.mark.asyncio
    async def test_macro_beat_table_has_correct_columns(self, temp_db_path, setup_db):
        """Test that macro_beat table has all required columns including Spec-038 fields (Spec-222: memory_snapshot eliminado)."""
        conn = await get_connection()

        cursor = await conn.execute("PRAGMA table_info(macro_beat)")
        rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        await conn.close()

        required = {
            "id",
            "story_id",
            "number",
            "summary",
            "synopsis_beat",
            "generated_act",
            "status",
            "active_scenario_id",
            "system_prompt",
            "user_prompt",
            "created_at",
        }
        assert required.issubset(columns), f"Missing: {required - columns}"

    @pytest.mark.asyncio
    async def test_narrative_journal_table_has_correct_columns(self, temp_db_path, setup_db):
        """Test that narrative_journal table has all required columns."""
        conn = await get_connection()

        cursor = await conn.execute("PRAGMA table_info(narrative_journal)")
        rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        await conn.close()

        required = {
            "id",
            "story_id",
            "last_events",
            "unresolved_mysteries",
            "physical_emotional_state",
        }
        assert required.issubset(columns), f"Missing: {required - columns}"

    @pytest.mark.asyncio
    async def test_scenario_table_has_correct_columns(self, temp_db_path, setup_db):
        """Test scenario table columns (Spec-038)."""
        conn = await get_connection()
        cursor = await conn.execute("PRAGMA table_info(scenario)")
        rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        await conn.close()
        assert {"id", "story_id", "order_index", "name"}.issubset(columns)

    @pytest.mark.asyncio
    async def test_narrative_anchors_table_has_correct_columns(self, temp_db_path, setup_db):
        """Test narrative_anchors table columns (Spec-038)."""
        conn = await get_connection()
        cursor = await conn.execute("PRAGMA table_info(narrative_anchors)")
        rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        await conn.close()
        assert {
            "id",
            "story_id",
            "resonance_hamartia",
            "resonance_hybris",
            "resonance_anagnorisis",
            "resonance_peripeteia",
            "resonance_residual",
        }.issubset(columns)

    @pytest.mark.asyncio
    async def test_generation_job_table_has_correct_columns(self, temp_db_path, setup_db):
        """Spec-460 T1.2: tabla generation_job."""
        conn = await get_connection()
        cursor = await conn.execute("PRAGMA table_info(generation_job)")
        columns = {row["name"] for row in await cursor.fetchall()}
        await conn.close()

        required = {
            "id",
            "story_id",
            "kind",
            "status",
            "stage",
            "beat",
            "total_beats",
            "params",
            "error",
            "narrative_id",
            "created_at",
            "started_at",
            "finished_at",
        }
        assert required.issubset(columns), f"Missing: {required - columns}"

    @pytest.mark.asyncio
    async def test_generation_job_un_solo_job_activo_por_historia(self, temp_db_path, setup_db):
        """Spec-460 T1.2: el índice único parcial rechaza un segundo job activo."""
        import sqlite3

        conn = await get_connection()
        await conn.execute("INSERT INTO story (id, title) VALUES ('s1', 't')")
        insert = (
            "INSERT INTO generation_job (id, story_id, kind, status, created_at) "
            "VALUES (?, 's1', 'full_generation', ?, '2026-09-22T00:00:00')"
        )
        await conn.execute(insert, ("j1", "done"))
        await conn.execute(insert, ("j2", "running"))  # un terminado + un activo: OK
        with pytest.raises(sqlite3.IntegrityError):
            await conn.execute(insert, ("j3", "queued"))
        await conn.close()

    @pytest.mark.asyncio
    async def test_init_db_es_idempotente(self, temp_db_path, setup_db):
        """init_db() se ejecuta en cada arranque: correrlo de nuevo no falla."""
        await init_db()
