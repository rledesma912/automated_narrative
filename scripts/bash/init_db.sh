#!/bin/bash
# Script para inicializar la base de datos

set -e

cd "$(dirname "$0")/../.."

echo "Inicializando base de datos..."

PYTHONPATH=. uv run python -c "
import asyncio
from src.infrastructure.database.connection import init_db

async def main():
    await init_db()
    print('Base de datos inicializada correctamente!')

asyncio.run(main())
"

echo "Listo!"