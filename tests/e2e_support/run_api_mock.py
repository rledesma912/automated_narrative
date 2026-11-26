"""API del Core para los E2E de Playwright (Spec-460 S4).

Levanta `src.main:app` con:
- una DB descartable sembrada por `seed_e2e_db.py` (historias de
  `input_stories/` generadas con el mock, Spec-440 T2.6) → los tests no tocan
  datos reales y arrancan siempre del mismo estado;
- el LLM reemplazado por `MockLLMAdapter` con una demora por llamada
  (`E2E_LLM_DELAY`) para que el avance en vivo sea observable.

Variables: E2E_DB (destino), E2E_LLM_DELAY (segundos, default 0.15),
E2E_API_PORT (default 8021), LLM_PROFILE_<LARGO> (Spec-740: solo para el Core, no la siembra).

Spec-700 D25/D26: el Revisor corre como en un perfil con el rol; si la idea dice
«SIN CRÉDITO», la API «no atiende» y queda la nota con lo que cambió.
Spec-720 D7: con «NUBE CAÍDA» en la historia, el Planificador y el Verificador
responden «desde el respaldo» (como si la nube no hubiera atendido).
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

# Spec-740 C6: la siembra escribe historias de cada largo con el mock; un largo deshabilitado
# (`LLM_PROFILE_MEDIO=off`, por ejemplo) es solo para el Core que prueban los E2E.
seed_env = {k: v for k, v in os.environ.items() if not k.startswith("LLM_PROFILE_")}
subprocess.run(
    [sys.executable, str(Path(__file__).with_name("seed_e2e_db.py")), str(db_path)],
    check=True,
    env=seed_env,
)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

from src.application.services.authoring import revisor  # noqa: E402
from src.config import settings  # noqa: E402 — después de fijar DATABASE_URL
from src.domain.exceptions import LLMUnavailableError  # noqa: E402
from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

settings.database_url = os.environ["DATABASE_URL"]

# Spec-795: una entrega de prueba en el tablero (carpeta descartable, al lado de la DB).
_tablero = db_path.parent / "tablero"
import shutil  # noqa: E402

from PIL import Image  # noqa: E402

shutil.rmtree(_tablero, ignore_errors=True)
_entrega = _tablero / "2026-11-26-calabaza-prueba-e2e"
_entrega.mkdir(parents=True)
for _nombre, _color in (("a.png", (90, 60, 120)), ("b.png", (30, 30, 30))):
    Image.new("RGB", (80, 60), _color).save(_entrega / _nombre)
(_entrega / "entrega.yaml").write_text(
    "titulo: Prueba del tablero\nproyecto: calabaza\nque_mirar: Elegí **una**.\n"
    "filas:\n  - titulo: Maestra\n    imagenes:\n"
    "      - {archivo: a.png, leyenda: Opción A}\n      - {archivo: b.png, leyenda: Opción B}\n",
    encoding="utf-8",
)


class SlowMockLLM(MockLLMAdapter):
    def __init__(self):
        super().__init__()
        self.respaldos: set[str] = set()

    async def generate(self, prompt, *args, **kwargs):
        await asyncio.sleep(delay)
        role = kwargs.get("role")
        if role in ("planificador", "verificador") and "NUBE CAÍDA" in prompt:
            self.respaldos.add(role)
        if kwargs.get("role") == "revisor" and "SIN CRÉDITO" in prompt:
            raise LLMUnavailableError("credito", "La IA de la nube no atiende.")
        return await super().generate(prompt, *args, **kwargs)


revisor.con_ia = lambda: True


from src.infrastructure.adapters.registro_llm import RegistroLLM  # noqa: E402

# Spec-740 B: con el registro, como la factory real («Lo escribió …» en «El relato»).
LLMFactory.get_provider = staticmethod(lambda *_a, **_k: RegistroLLM(SlowMockLLM()))

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="127.0.0.1", port=port, log_level="warning")
