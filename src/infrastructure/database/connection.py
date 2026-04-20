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
            escenarios TEXT,
            sinopsis TEXT,
            atmosfera TEXT,
            narrative_brief TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS beat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            number INTEGER NOT NULL,
            summary TEXT NOT NULL,
            content TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            technical_context TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES story(id),
            UNIQUE(story_id, number)
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
