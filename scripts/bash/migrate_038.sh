#!/bin/bash
# Migración Spec-038: beat → macro_beat + tablas scenario y narrative_anchors
# Uso: ./scripts/bash/migrate_038.sh [ruta_db]
# Si no se pasa ruta, usa stories.db del directorio raíz del proyecto.

set -e
cd "$(dirname "$0")/../.."

DB_PATH="${1:-stories.db}"

if [ ! -f "$DB_PATH" ]; then
    echo "Base de datos no encontrada: $DB_PATH"
    echo "Para bases nuevas, usá init_db.sh. Para bases existentes, pasá la ruta como argumento."
    exit 1
fi

echo "Migrando $DB_PATH a Spec-038..."

sqlite3 "$DB_PATH" <<'SQL'

-- 1. Crear tabla macro_beat con la nueva estructura
CREATE TABLE IF NOT EXISTS macro_beat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    summary TEXT NOT NULL,
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    technical_context TEXT,
    active_scenario_id TEXT REFERENCES scenario(id),
    narrative_context TEXT,
    memory_snapshot TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES story(id),
    UNIQUE(story_id, number)
);

-- 2. Migrar datos existentes de beat → macro_beat
INSERT OR IGNORE INTO macro_beat
    (id, story_id, number, summary, content, status, technical_context, created_at)
SELECT id, story_id, number, summary, content, status, technical_context, created_at
FROM beat;

-- 3. Crear tabla scenario
CREATE TABLE IF NOT EXISTS scenario (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL REFERENCES story(id),
    order_index INTEGER NOT NULL,
    name TEXT NOT NULL
);

-- 4. Crear tabla narrative_anchors
CREATE TABLE IF NOT EXISTS narrative_anchors (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL UNIQUE REFERENCES story(id),
    initial_state TEXT NOT NULL,
    threat_nature TEXT NOT NULL,
    horror_peak TEXT NOT NULL,
    spatial_anchor TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

SQL

echo "Migración completada."
echo "Nota: La tabla 'beat' original se conserva. Podés eliminarla manualmente con:"
echo "  sqlite3 $DB_PATH 'DROP TABLE beat;'"
