"""Spec-790 T3.3: snapshot de los prompts de la miniatura (sin LLM ni GPU).

El prompt de la IA que separa las descripciones y las 4 plantillas de imagen, llenas con la
salida del mock. Para regenerarlo a propósito:
    SNAPSHOT_UPDATE=1 uv run pytest tests/unit/application/miniatura/test_thumbnail_prompts_snapshot.py
"""

import json
import os
import re
from pathlib import Path

from src.application.services.miniatura import textos
from src.application.services.miniatura.arte import prompt, texto
from src.domain.thumbnail import ThumbnailInput
from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter

SNAPSHOT = Path(__file__).parents[3] / "fixtures" / "snapshots" / "thumbnail_prompts.json"
_INPUT = ThumbnailInput(
    figure_description=(
        "Peter, un conejo altísimo y flaco, con orejas largas, ojos amarillos que brillan y "
        "garras. Que resalte del fondo y parezca hiperrealista."
    ),
    place_description="Un bosque de noche con plantas y pasto, y niebla al fondo.",
)
_PASOS = ("personaje", "fotografiar_personaje", "escenario", "fotografiar_escenario")


async def _prompts() -> dict:
    txt = await textos.separar(MockLLMAdapter(), _INPUT, "h")
    return {
        "ia_sistema": texto("ia_sistema"),
        "ia_pedido": textos.pedido(_INPUT),
        **{
            paso: prompt(paso, txt.personaje if "personaje" in paso else txt.escenario)
            for paso in _PASOS
        },
    }


async def test_snapshot_de_los_prompts_de_la_miniatura():
    prompts = await _prompts()
    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert prompts == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


async def test_la_ia_recibe_las_dos_descripciones_y_los_bocetos():
    p = await _prompts()
    assert _INPUT.figure_description in p["ia_pedido"]
    assert _INPUT.place_description in p["ia_pedido"]
    for seccion in ("bocetos", "personaje:", "escenario:", "relacion:", "a_medio_ver:", "positivo"):
        assert seccion in p["ia_sistema"], seccion


async def test_las_plantillas_de_imagen_llevan_la_descripcion_y_ningun_material_de_mas():
    """E11c: la caseta venía de los materiales de edificios del prompt de «fotografiar»."""
    p = await _prompts()
    for paso in _PASOS:
        assert "{descripcion}" not in p[paso], paso
        for material in ("roof tiles", "weathered wood", "old stone"):
            assert material not in p[paso], (paso, material)


async def test_la_foto_del_escenario_va_en_positivo():
    """D27: Z-Image no ve el boceto y corre con cfg 1: lo que se niega, lo dibuja. Los prompts
    de Qwen y la foto del personaje conservan sus negaciones (E11 y E11e se validaron así)."""
    p = await _prompts()
    assert not re.search(r"\b(no|not|without|nobody)\b", p["fotografiar_escenario"], re.I)
    assert "empty and lonely" in p["fotografiar_escenario"]
