"""Spec-610 T2.2: snapshot del prompt del paquete para el video (sin LLM).

Para regenerarlo a propósito:
    SNAPSHOT_UPDATE=1 uv run pytest tests/unit/application/video/test_video_prompts_snapshot.py
"""

import json
import os
import uuid
from pathlib import Path

from src.application.services import narrative_acts
from src.application.services.video.config import video_config
from src.application.services.video.prompts import VideoScriptPrompts
from src.domain.models import ActOutline, Entity, RevealLevel, Story

SNAPSHOT = Path(__file__).parents[3] / "fixtures" / "snapshots" / "video_prompts.json"
STORY_ID = uuid.UUID("00000000-0000-4000-8000-000000000610")
CONTENT = (
    "## Acto 1\n\nNunca se lo conté a nadie.\n\nEsa noche venía manejando por el bosque.\n\n"
    "## Acto 2\n\nBajé a mirar el motor.\n\nHabía siluetas entre los troncos.\n\n"
    "## Acto 3\n\nCorrí hasta el pueblo."
)


def _story() -> Story:
    return Story(
        id=STORY_ID,
        title="No te detengas en el bosque",
        protagonista="Ernesto: camionero",
        relator="Primera persona. Narrador: Ernesto.",
        sinopsis="Un camión se queda en el bosque.",
        outline=[
            ActOutline(number=1, scenario="La ruta del Bosque del Silencio"),
            ActOutline(number=2, scenario="El borde del bosque"),
            ActOutline(number=3, scenario=""),
        ],
        entities=[
            Entity(
                story_id=STORY_ID,
                order_index=0,
                name="Los de las astas",
                nature_id="desconocida",
                description="Siluetas iguales con astas.",
                manifestations="ojos que brillan; murmullo",
                reveal_level=RevealLevel.PROGRESIVA,
            )
        ],
    )


def _prompts() -> dict:
    builder = VideoScriptPrompts(video_config())
    acts = narrative_acts.split(CONTENT)
    system, user = builder.build(_story(), acts)
    _, retry = builder.build(_story(), acts, ["El outro tiene que terminar con «Buenas noches»."])
    return {"system": system, "user": user, "user_reintento": retry}


def test_snapshot_del_prompt_del_paquete():
    prompts = _prompts()
    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert prompts == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_el_prompt_trae_todas_sus_secciones():
    p = _prompts()
    user = p["user"]
    for seccion in (
        "EL RELATO «No te detengas en el bosque», ACTO POR ACTO",
        "ACTO 1 (",
        "[2] Esa noche venía manejando por el bosque.",
        "DÓNDE PASA CADA ACTO",
        "- Acto 1: La ruta del Bosque del Silencio.",
        "- Acto 3: un lugar que no dice la historia.",
        "La amenaza:",
        "LA CALABAZA DE LA CRIPTA (EL PRESENTADOR)",
        "OUTROS DE OTROS EPISODIOS",
        "Me gusta pensar que Alejandro tuvo suerte.",
        "LO QUE VA EN PANTALLA",
        "people, person",
        "entre 5 y 5 momentos",  # el relato tiene 5 párrafos: no pide más
        "Fundido desde negro, Corte",
    ):
        assert seccion in user, seccion
    assert "LA RESPUESTA ANTERIOR TENÍA ESTOS PROBLEMAS" not in user
    assert "- El outro tiene que terminar con «Buenas noches»." in p["user_reintento"]
    assert "La calabaza de la cripta" in p["system"]
