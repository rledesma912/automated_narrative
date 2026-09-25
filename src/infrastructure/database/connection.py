"""Database connection."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

from src.config import settings
from src.infrastructure.database.seeds.entity_natures import genre_nature_rows, nature_rows
from src.infrastructure.database.seeds.genre_catalog import genre_rows, subgenre_rows


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


@asynccontextmanager
async def connection() -> AsyncIterator[aiosqlite.Connection]:
    """Conexión que se cierra siempre, también ante una excepción.

    Una conexión aiosqlite sin cerrar deja vivo su hilo y puede colgar el proceso
    (p. ej. `export-yaml` sobre un esquema viejo).
    """
    conn = await get_connection()
    try:
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    """Initialize database tables."""
    conn = await get_connection()

    # Spec-440 §2: catálogo de géneros. La PK compuesta permite `otro` en cada género.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS genre (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            order_index INTEGER NOT NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS subgenre (
            genre_id TEXT NOT NULL,
            id TEXT NOT NULL,
            label TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            PRIMARY KEY (genre_id, id),
            FOREIGN KEY (genre_id) REFERENCES genre(id) ON DELETE RESTRICT
        )
    """)
    await conn.executemany(
        "INSERT OR IGNORE INTO genre (id, label, order_index) VALUES (?, ?, ?)", genre_rows()
    )
    await conn.executemany(
        "INSERT OR IGNORE INTO subgenre (genre_id, id, label, order_index) VALUES (?, ?, ?, ?)",
        subgenre_rows(),
    )

    # Spec-450 §1: naturalezas de entidad. El seed manda (upsert); el mapeo solo agrega.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_nature (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            order_index INTEGER NOT NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS genre_entity_nature (
            genre_id TEXT NOT NULL,
            nature_id TEXT NOT NULL,
            PRIMARY KEY (genre_id, nature_id),
            FOREIGN KEY (genre_id) REFERENCES genre(id),
            FOREIGN KEY (nature_id) REFERENCES entity_nature(id)
        )
    """)
    await conn.executemany(
        "INSERT INTO entity_nature (id, label, order_index) VALUES (?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET label = excluded.label, order_index = excluded.order_index",
        nature_rows(),
    )
    await conn.executemany(
        "INSERT OR IGNORE INTO genre_entity_nature (genre_id, nature_id) VALUES (?, ?)",
        genre_nature_rows(),
    )

    # genero/subgenero vacíos se guardan NULL: la FK compuesta no se verifica con un NULL.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS story (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            protagonista TEXT,
            relator TEXT,
            sinopsis TEXT,
            genero TEXT,
            subgenero TEXT,
            tono TEXT,
            narrator_config TEXT,
            direction TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (genero) REFERENCES genre(id),
            FOREIGN KEY (genero, subgenero) REFERENCES subgenre(genre_id, id)
        )
    """)

    # Spec-450 §1: entidades (máx. 3 por historia; order_index 0 = principal).
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS entity (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            name TEXT,
            nature_id TEXT NOT NULL,
            description TEXT DEFAULT '',
            manifestations TEXT DEFAULT '',
            limits TEXT DEFAULT '',
            reveal_level TEXT NOT NULL DEFAULT 'insinuada',
            UNIQUE (story_id, order_index),
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE,
            FOREIGN KEY (nature_id) REFERENCES entity_nature(id)
        )
    """)
    # Estado de las entidades por beat (lo escribe el Journal, Spec-450 §3). Cuelga
    # de `story` y no de `entity`: editar la historia reinserta las entidades con
    # ids nuevos y el estado del journal debe sobrevivir.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_journal (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            beat_number INTEGER NOT NULL,
            entity_state TEXT NOT NULL DEFAULT '',
            UNIQUE (story_id, beat_number),
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS character (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT,
            traits TEXT DEFAULT '[]',
            kind TEXT NOT NULL DEFAULT 'persona',
            relation TEXT DEFAULT '',
            order_index INTEGER NOT NULL,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rule (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT,
            intensity TEXT,
            applies_to_beat INTEGER,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE,
            CHECK (applies_to_beat IS NULL OR applies_to_beat >= 1)
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
        CREATE TABLE IF NOT EXISTS scenario (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
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

    # Spec-530: taller del asistente. Una fila por criterio y nivel, con la pregunta
    # vigente, la respuesta y las preguntas de rondas anteriores (`asked`).
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS story_workshop (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            level TEXT NOT NULL DEFAULT 'direccion',
            criterion TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'falta',
            question TEXT DEFAULT '',
            options TEXT DEFAULT '[]',
            answer TEXT DEFAULT '',
            round INTEGER NOT NULL DEFAULT 1,
            question_round INTEGER NOT NULL DEFAULT 0,
            asked TEXT DEFAULT '[]',
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE,
            UNIQUE (story_id, level, criterion)
        )
    """)
    # Spec-530: escaleta (entrada de cada acto; `macro_beat` es la salida generada).
    # Escenario y personajes en escena van por nombre: se reescriben con ids nuevos.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS act_outline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            number INTEGER NOT NULL CHECK (number BETWEEN 1 AND 5),
            goal TEXT DEFAULT '',
            events TEXT DEFAULT '[]',
            change_from TEXT DEFAULT '',
            change_to TEXT DEFAULT '',
            scenario TEXT DEFAULT '',
            on_stage TEXT DEFAULT '[]',
            held_back TEXT DEFAULT '',
            seeds TEXT DEFAULT '[]',
            payoffs TEXT DEFAULT '[]',
            decisions TEXT DEFAULT '[]',
            warnings TEXT DEFAULT '[]',
            needs_review INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE,
            UNIQUE (story_id, number)
        )
    """)

    # Spec-460: jobs de generación asíncrona.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS generation_job (
            id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT,
            beat INTEGER,
            total_beats INTEGER,
            params TEXT DEFAULT '{}',
            error TEXT,
            narrative_id TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generation_job_story_status
        ON generation_job(story_id, status)
    """)
    # Un solo job activo por historia: la idempotencia también la garantiza la DB.
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_generation_job_active_story
        ON generation_job(story_id) WHERE status IN ('queued', 'running')
    """)

    await conn.commit()
    await conn.close()
