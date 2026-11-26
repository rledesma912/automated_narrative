"""`config/tablero.yaml` (Spec-795 §2.3), validado al cargar."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

ARCHIVO = Path("config/tablero.yaml")


class TableroConfig(BaseModel):
    proyectos: dict[str, str] = {}
    tope_mb_por_archivo: float = Field(20, gt=0)
    extensiones: list[str] = Field(min_length=1)

    def nombre_de(self, proyecto: str) -> str:
        return self.proyectos.get(proyecto, proyecto)


@lru_cache(maxsize=1)
def tablero_config() -> TableroConfig:
    return TableroConfig.model_validate(yaml.safe_load(ARCHIVO.read_text(encoding="utf-8")))
