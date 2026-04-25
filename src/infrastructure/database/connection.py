"""Database connection."""

import aiosqlite

from src.config import settings


async def get_connection() -> aiosqlite.Connection:
    """Get database connection."""
    db_url = settings.database_url.replace("sqlite+aiosqlite://", "")
    conn = await aiosqlite.connect(db_url)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db() -> None:
    """Initialize database tables."""
    conn = await get_connection()

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS story (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            protagonista TEXT,
            relator TEXT,
            sinopsis TEXT,
            atmosfera TEXT,
            narrative_brief TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rule (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (story_id) REFERENCES story(id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS macro_beat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            number INTEGER NOT NULL,
            summary TEXT NOT NULL,
            content TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            technical_context TEXT,
            active_scenario_id TEXT REFERENCES scenario(id),
            active_scenario_description TEXT,
            narrative_context TEXT,
            memory_snapshot TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES story(id),
            UNIQUE(story_id, number)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS macro_beat_rule (
            macro_beat_id INTEGER NOT NULL,
            rule_id TEXT NOT NULL,
            PRIMARY KEY (macro_beat_id, rule_id),
            FOREIGN KEY (macro_beat_id) REFERENCES macro_beat(id) ON DELETE CASCADE,
            FOREIGN KEY (rule_id) REFERENCES rule(id) ON DELETE CASCADE
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS scenario (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL REFERENCES story(id),
            order_index INTEGER NOT NULL,
            name TEXT NOT NULL
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS narrative_anchors (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL UNIQUE REFERENCES story(id),
            initial_state TEXT NOT NULL,
            threat_nature TEXT NOT NULL,
            horror_peak TEXT NOT NULL,
            spatial_anchor TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS narrative_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT UNIQUE NOT NULL,
            last_events TEXT DEFAULT '',
            unresolved_mysteries TEXT DEFAULT '',
            physical_emotional_state TEXT DEFAULT ''
        )
    """)

    await conn.commit()
    await conn.close()
