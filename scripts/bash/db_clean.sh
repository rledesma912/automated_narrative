#!/bin/bash
# Limpia la base de datos - acepta ID de historia para eliminación selectiva.

set -e
cd "$(dirname "$0")/../.."

DB_FILE="data/dev/stories.db"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TARGET_ID="$1"

if [ -n "$TARGET_ID" ]; then
    echo -e "${YELLOW}Eliminación selectiva: historial con ID=$TARGET_ID${NC}"
    read -p "¿Continuar? (y/N): " confirm
else
    echo -e "${YELLOW}ADVERTENCIA: Esta acción eliminará TODOS los registros.${NC}"
    read -p "¿Estás seguro de que deseas continuar? (y/N): " confirm
fi

if [[ $confirm != [yY] ]]; then
    echo "Operación cancelada."
    exit 0
fi

if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}Error: El archivo '$DB_FILE' no existe.${NC}"
    exit 1
fi

echo "Limpiando base de datos..."

python3 -c "
import sqlite3
import sys

conn = sqlite3.connect('$DB_FILE')
cursor = conn.cursor()
cursor.execute('PRAGMA foreign_keys = ON;')

target_id = '$TARGET_ID' if '$TARGET_ID' else None

if target_id:
    tables = [
        'generated_narrative',
        'macro_beat',
        'narrative_journal',
        'narrative_anchors',
        'rule',
        'scenario',
    ]
    for table in tables:
        try:
            cursor.execute(f'DELETE FROM {table} WHERE story_id = ? OR story_template_id = ?;', (target_id, target_id))
            print(f'Tabla {table}: eliminados', cursor.rowcount, 'registros.')
        except sqlite3.OperationalError as e:
            print(f'Tabla {table}: omitida ({e})')
    cursor.execute('DELETE FROM story WHERE id = ?;', (target_id,))
    print(f'Tabla story: eliminados', cursor.rowcount, 'registros.')
else:
    tables = [
        'generated_narrative',
        'rule',
        'macro_beat',
        'narrative_anchors',
        'narrative_journal',
        'scenario',
        'story',
    ]
    for table in tables:
        cursor.execute(f'DELETE FROM {table};')
        print(f'Tabla {table} limpiada.')
    cursor.execute(\"DELETE FROM sqlite_sequence WHERE name IN ('macro_beat', 'narrative_journal');\")

conn.commit()
cursor.execute('VACUUM;')
conn.close()
print('Limpieza completada.')
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Operación finalizada.${NC}"
else
    echo -e "${RED}Ocurrió un error durante la limpieza.${NC}"
    exit 1
fi