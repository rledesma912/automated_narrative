#!/bin/bash
# Inicializar base de datos

cd "$(dirname "$0")/.."

echo "📦 Inicializando base de datos..."

PYTHONPATH=. uv run python -c "
import asyncio
from src.infrastructure.database.connection import init_db

async def main():
    await init_db()
    print('✅ Base de datos inicializada')

asyncio.run(main())
"