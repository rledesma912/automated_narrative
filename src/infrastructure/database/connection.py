"""Database connection."""

import aiosqlite

from src.config import settings


async def get_connection() -> aiosqlite.Connection:
    """Get database connection.

    Convención SQLAlchemy para SQLite:
      - `sqlite+aiosqlite:///foo.db`   → relativo `foo.db`
      - `sqlite+aiosqlite:////abs.db`  → absoluto `/abs.db`
    """
    raw = settings.database_url
    if raw.startswith("sqlite+aiosqlite:////"):
        db_url = "/" + raw[len("sqlite+aiosqlite:////") :]
    elif raw.startswith("sqlite+aiosqlite:///"):
        db_url = raw[len("sqlite+aiosqlite:///") :]
    elif raw.startswith("sqlite+aiosqlite://"):
        db_url = raw[len("sqlite+aiosqlite://") :]
    else:
        db_url = raw
    conn = await aiosqlite.connect(db_url, timeout=30.0)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA journal_mode = WAL")
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
            storyteller_config TEXT,
            personajes TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rule (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT,
            intensity TEXT,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS macro_beat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            number INTEGER NOT NULL,
            summary TEXT NOT NULL,
            synopsis_beat TEXT,
            generated_act TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            active_scenario_id TEXT,
            active_scenario_description TEXT,
            system_prompt TEXT,
            user_prompt TEXT,
            type TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE,
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
            story_id TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS narrative_anchors (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            resonance_hamartia TEXT NOT NULL,
            resonance_hybris TEXT NOT NULL,
            resonance_anagnorisis TEXT NOT NULL,
            resonance_peripeteia TEXT NOT NULL,
            resonance_residual TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS narrative_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            beat_number INTEGER NOT NULL,
            last_events TEXT DEFAULT '',
            unresolved_mysteries TEXT DEFAULT '',
            physical_emotional_state TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE,
            UNIQUE(story_id, beat_number)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS generated_narrative (
            id TEXT PRIMARY KEY,
            story_template_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_template_id) REFERENCES story(id) ON DELETE CASCADE
        )
    """)

    await conn.commit()
    await conn.close()
