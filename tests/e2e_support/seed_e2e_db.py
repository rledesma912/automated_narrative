"""Semilla de la DB de los E2E (Spec-440 T2.6).

Crea una DB vacía, importa `input_stories/*.yaml` (como `import-yaml`) y genera
cada historia con el LLM mock: quedan `completed` con un relato. Corre en su
propio proceso para que el loop de la semilla no se cruce con el del servidor.

Uso: python tests/e2e_support/seed_e2e_db.py <ruta.db>
"""

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
db_path = Path(sys.argv[1])
for suffix in ("", "-wal", "-shm"):
    Path(f"{db_path}{suffix}").unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

import httpx  # noqa: E402

from src.cli import commands  # noqa: E402
from src.config import settings  # noqa: E402
from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

settings.database_url = os.environ["DATABASE_URL"]
# Texto distinto del mock del servidor: regenerar un acto en los E2E tiene que
# producir un cambio visible (como con la semilla real de antes).
LLMFactory.get_provider = staticmethod(
    lambda *_a, **_k: MockLLMAdapter("Contenido de la semilla E2E")
)


async def seed() -> None:
    from uuid import UUID

    from src.main import app
    from src.presentation.runtime import job_manager

    files = sorted((REPO_ROOT / "input_stories").glob("*.yaml"))
    if await commands._import_yaml_async(files, drop_invalid_subgenre=False):
        raise SystemExit("seed E2E: hay YAML de input_stories que no se importan")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://seed") as client:
        stories = (await client.get("/api/v1/stories")).json()
        for story in stories:
            resp = await client.post(f"/api/v1/stories/{story['id']}/jobs", json={})
            resp.raise_for_status()
            await job_manager.wait(UUID(resp.json()["job_id"]))
        for story in (await client.get("/api/v1/stories")).json():
            if story["status"] != "completed":
                raise SystemExit(f"seed E2E: '{story['title']}' quedó {story['status']}")
            print(f"seed E2E: {story['title']} ({story['id']})")


if __name__ == "__main__":
    asyncio.run(seed())
