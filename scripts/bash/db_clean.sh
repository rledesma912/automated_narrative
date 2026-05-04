#!/bin/bash
# Limpia todos los registros de la base de datos (respeta FK order).

set -e
cd "$(dirname "$0")/../.."

DB_FILE="data/stories.db"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}ADVERTENCIA: Esta acción eliminará todos los registros de las 5 tablas.${NC}"
read -p "¿Estás seguro de que deseas continuar? (y/N): " confirm

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

conn = sqlite3.connect('$DB_FILE')
cursor = conn.cursor()
cursor.execute('PRAGMA foreign_keys = ON;')

tables_order = [
    'macro_beat_rule',
    'rule',
    'macro_beat',
    'narrative_anchors',
    'narrative_journal',
    'scenario',
    'story',
]

for table in tables_order:
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