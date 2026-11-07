"""Spec-750 S1 (T1.1): la tabla `story` pasa a tres largos sin perder nada.

SQLite no cambia un CHECK con ALTER: `init_db()` reconstruye `story` cuando tiene el CHECK
viejo (`largo|corto`) y pasa las historias de 5 actos de `largo` a `medio`. Con las FK
prendidas, `DROP TABLE story` borraría en cascada todo lo demás: este test llena todas las
tablas hijas y compara los conteos.
"""

import json
import sqlite3

import pytest

from src.config import settings
from src.infrastructure.database.connection import init_db

OLD_STORY = """
    CREATE TABLE story (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        protagonista TEXT,
        relator TEXT,
        sinopsis TEXT,
        genero TEXT,
        subgenero TEXT,
        narrator_config TEXT,
        direction TEXT,
        -- Spec-650: estructura del relato (llm_beats_definition.yaml → estructuras)
        structure TEXT NOT NULL DEFAULT 'largo' CHECK (structure IN ('largo', 'corto')),
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (genero) REFERENCES genre(id),
        FOREIGN KEY (genero, subgenero) REFERENCES subgenre(genre_id, id)
    )
"""

CHILDREN = (
    "entity",
    "character",
    "rule",
    "macro_beat",
    "scenario",
    "narrative_journal",
    "generated_narrative",
    "story_workshop",
    "act_outline",
    "generation_job",
    "llm_call",
    "video_script",
)


def _story_sql(con) -> str:
    return con.execute("SELECT sql FROM sqlite_master WHERE name = 'story'").fetchone()[0]


def _to_old_schema(path):
    """La base como la tiene prod hoy: `story` con el CHECK de dos largos."""
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute("DROP TABLE story")
    con.execute(OLD_STORY)
    con.commit()
    con.close()


def _fill(path):
    """Una historia de cada largo, cada una con filas en todas las tablas hijas."""
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    for sid, structure in (("s-largo", "largo"), ("s-corto", "corto")):
        nid, jid = f"n-{sid}", f"j-{sid}"
        con.execute(
            "INSERT INTO story (id, title, structure, direction) VALUES (?, ?, ?, ?)",
            (sid, f"Historia {structure}", structure, json.dumps({"premisa": "x"})),
        )
        con.execute(
            "INSERT INTO entity (id, story_id, order_index, nature_id) "
            "VALUES (?, ?, 0, (SELECT id FROM entity_nature LIMIT 1))",
            (f"e-{sid}", sid),
        )
        con.execute(
            "INSERT INTO character (id, story_id, name, order_index) VALUES (?, ?, 'Ana', 0)",
            (f"c-{sid}", sid),
        )
        con.execute(
            "INSERT INTO rule (id, story_id, content) VALUES (?, ?, 'r')", (f"r-{sid}", sid)
        )
        con.execute("INSERT INTO macro_beat (story_id, number) VALUES (?, 1)", (sid,))
        con.execute(
            "INSERT INTO scenario (id, story_id, order_index, name) VALUES (?, ?, 0, 'casa')",
            (f"sc-{sid}", sid),
        )
        con.execute("INSERT INTO narrative_journal (story_id, beat_number) VALUES (?, 1)", (sid,))
        con.execute(
            "INSERT INTO generated_narrative (id, story_template_id, title, content) "
            "VALUES (?, ?, 't', 'c')",
            (nid, sid),
        )
        con.execute(
            "INSERT INTO story_workshop (story_id, level, criterion) VALUES (?, 'direccion', 'meta')",
            (sid,),
        )
        con.execute("INSERT INTO act_outline (story_id, number) VALUES (?, 1)", (sid,))
        con.execute(
            "INSERT INTO generation_job (id, story_id, kind, status, params, created_at) "
            "VALUES (?, ?, 'full_generation', 'done', ?, '2026-11-06')",
            (jid, sid, json.dumps({"structure": structure, "profile": "openai-sol"})),
        )
        con.execute(
            "INSERT INTO llm_call (story_id, job_id, narrative_id) VALUES (?, ?, ?)",
            (sid, jid, nid),
        )
        con.execute(
            "INSERT INTO video_script (id, narrative_id, data, parrafos_por_acto, "
            "narrative_hash, seed, created_at, updated_at) "
            "VALUES (?, ?, '{}', '{}', 'h', 1, '2026-11-06', '2026-11-06')",
            (f"v-{sid}", nid),
        )
    con.commit()
    con.close()


def _counts(path) -> dict[str, int]:
    con = sqlite3.connect(path)
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in CHILDREN}
    con.close()
    return counts


@pytest.fixture
async def old_db(monkeypatch, tmp_path):
    path = tmp_path / "vieja.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{path}")
    await init_db()
    _to_old_schema(path)
    _fill(path)
    return path


async def test_una_base_nueva_nace_con_los_tres_largos(monkeypatch, tmp_path):
    path = tmp_path / "nueva.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{path}")
    await init_db()

    con = sqlite3.connect(path)
    assert "('corto', 'medio', 'largo')" in _story_sql(con)
    con.execute("INSERT INTO story (id, title) VALUES ('s', 't')")
    assert con.execute("SELECT structure FROM story").fetchone()[0] == "medio"
    for structure in ("corto", "largo"):
        con.execute(
            "INSERT INTO story (id, title, structure) VALUES (?, 't', ?)", (structure, structure)
        )
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO story (id, title, structure) VALUES ('x', 't', 'extenso')")


async def test_la_reconstruccion_conserva_todo_y_pasa_largo_a_medio(old_db):
    antes = _counts(old_db)
    assert all(antes.values()), antes

    await init_db()

    assert _counts(old_db) == antes
    con = sqlite3.connect(old_db)
    assert "('corto', 'medio', 'largo')" in _story_sql(con)
    assert dict(con.execute("SELECT id, structure FROM story")) == {
        "s-largo": "medio",
        "s-corto": "corto",
    }
    params = {
        sid: json.loads(p) for sid, p in con.execute("SELECT story_id, params FROM generation_job")
    }
    assert params["s-largo"] == {"structure": "medio", "profile": "openai-sol"}
    assert params["s-corto"]["structure"] == "corto"
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    # Las FK siguen vivas: borrar la historia se lleva sus filas.
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("DELETE FROM story WHERE id = 's-corto'")
    assert set(_counts_con(con).values()) == {1}


def _counts_con(con) -> dict[str, int]:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in CHILDREN}


async def test_correrla_dos_veces_no_cambia_nada(old_db):
    await init_db()
    con = sqlite3.connect(old_db)
    sql, filas = _story_sql(con), con.execute("SELECT * FROM story ORDER BY id").fetchall()
    con.close()

    await init_db()

    con = sqlite3.connect(old_db)
    assert _story_sql(con) == sql
    assert con.execute("SELECT * FROM story ORDER BY id").fetchall() == filas
