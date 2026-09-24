"""API del Core para los E2E de Playwright (Spec-460 S4).

Levanta `src.main:app` con:
- una DB descartable sembrada por `seed_e2e_db.py` (historias de
  `input_stories/` generadas con el mock, Spec-440 T2.6) → los tests no tocan
  datos reales y arrancan siempre del mismo estado;
- el LLM reemplazado por `MockLLMAdapter` con una demora por llamada
  (`E2E_LLM_DELAY`) para que el avance en vivo sea observable.

Variables: E2E_DB (destino), E2E_LLM_DELAY (segundos, default 0.15),
E2E_API_PORT (default 8021).
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import uvicorn

db_path = Path(os.environ["E2E_DB"])
delay = float(os.environ.get("E2E_LLM_DELAY", "0.15"))
port = int(os.environ.get("E2E_API_PORT", "8021"))

subprocess.run(
    [sys.executable, str(Path(__file__).with_name("seed_e2e_db.py")), str(db_path)], check=True
)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

from src.config import settings  # noqa: E402 — después de fijar DATABASE_URL
from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

settings.database_url = os.environ["DATABASE_URL"]


class SlowMockLLM(MockLLMAdapter):
    async def generate(self, *args, **kwargs):
        await asyncio.sleep(delay)
        return await super().generate(*args, **kwargs)


LLMFactory.get_provider = staticmethod(lambda *_a, **_k: SlowMockLLM())

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="127.0.0.1", port=port, log_level="warning")
