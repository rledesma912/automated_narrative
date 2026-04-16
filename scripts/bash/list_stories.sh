#!/bin/bash
# Script para listar todas las historias

set -e

cd "$(dirname "$0")/../.."

PYTHONPATH=. uv run python -c "
import asyncio
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLStoryRepository

async def main():
    await init_db()
    repo = SQLStoryRepository()
    stories = await repo.list_all()
    
    if not stories:
        print('No hay historias en la base de datos.')
        return
    
    print('Historias en la base de datos:')
    print('-' * 80)
    for s in stories:
        print(f'ID: {s.id}')
        print(f'Título: {s.title}')
        print(f'Status: {s.status}')
        print('-' * 80)

asyncio.run(main())
"