#!/bin/bash
# Script para limpiar los registros de la base de datos NarrativeForge usando Python

DB_FILE="stories.db"

# Colores para salida
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}ADVERTENCIA: Esta acción eliminará todos los registros de 'story', 'beat' y 'narrative_journal'.${NC}"
read -p "¿Estás seguro de que deseas continuar? (y/N): " confirm

if [[ $confirm != [yY] ]]; then
    echo "Operación cancelada."
    exit 0
fi

if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}Error: El archivo de base de datos '$DB_FILE' no existe.${NC}"
    exit 1
fi

echo "Limpiando base de datos..."

# Usar python para ejecutar el SQL ya que sqlite3 no está en el PATH
python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('$DB_FILE')
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')
    
    # Eliminar en orden de cascada
    tables = ['narrative_journal', 'beat', 'story']
    for table in tables:
        cursor.execute(f'DELETE FROM {table};')
        print(f'Tabla {table} limpiada.')
    
    # Resetear secuencias
    cursor.execute(\"DELETE FROM sqlite_sequence WHERE name IN ('beat', 'narrative_journal');\")
    
    conn.commit()
    cursor.execute('VACUUM;')
    conn.close()
    print('Limpieza completada exitosamente.')
except Exception as e:
    print(f'Error: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Operación finalizada.${NC}"
else
    echo -e "${RED}Ocurrió un error durante la limpieza.${NC}"
    exit 1
fi
