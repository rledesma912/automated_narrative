"""Snapshot de los prompts del asistente: Consultor, Planificador y Verificador (Spec-620).

El snapshot del pipeline (`tests/integration/test_pipeline_prompts_snapshot.py`) arma la
escaleta desde cero: no pasa por el Consultor ni por varias secciones del Planificador y
el Verificador (decisiones con pregunta, receta del efecto, borradores, problemas de la
revisión, decisiones por acto). Este arma los tres prompts directamente con una historia
que las activa todas.

Para regenerarlo a propósito:
    SNAPSHOT_UPDATE=1 uv run pytest tests/unit/application/authoring/test_assistant_prompts_snapshot.py
"""

import json
import os
from pathlib import Path

from src.application.services.authoring.consultant import WorkshopConsultant
from src.application.services.authoring.planner import OutlinePlanner
from src.application.services.authoring.verifier import OutlineVerifier
from src.domain.models import (
    ActOutline,
    CriterionStatus,
    Direction,
    OutlineWarning,
    Story,
    WorkshopItem,
)

SNAPSHOT = Path(__file__).parents[3] / "fixtures" / "snapshots" / "assistant_prompts.json"


def _story() -> Story:
    acts = [
        ActOutline(
            number=n,
            bridge="" if n == 1 else f"Pasaron dos horas desde el acto {n - 1}.",
            goal=f"Que el micro llegue a la terminal (acto {n})",
            events=[f"Hecho {n}.1", f"Hecho {n}.2"],
            scenario="Ruta 36" if n % 2 else "",
            held_back="Que la mujer murió en ese asiento" if n == 2 else "",
            reveal_act=4 if n == 2 else 0,
            decisions=["meta"] if n == 1 else (["transgresion"] if n == 2 else []),
            warnings=[
                OutlineWarning(text=f"El acto {n} repite el hecho anterior."),
                OutlineWarning(text="Aviso ya ignorado.", dismissed=True),
            ]
            if n == 3
            else [],
            synopsis="José arranca el último recorrido." if n == 1 else "",
        )
        for n in range(1, 6)
    ]
    return Story(
        title="la pena del colectivo",
        protagonista="José: chofer de micros",
        relator="Primera persona. Narrador: José.",
        sinopsis="José ve por el espejo a una mujer que murió en su micro.",
        genero="sobrenatural",
        subgenero="fantasmas",
        narrator_config={"storyteller_name": "José"},
        personajes_full=[
            {"name": "José", "role": "Chofer"},
            {"name": "Marta", "relation": "pasajera de todas las noches"},
        ],
        direction=Direction(
            premise="José ve por el espejo a una mujer que murió en su micro.",
            effect="revelacion",
            ending="Descansa en paz.",
            ending_intentional=True,
            telling="caso",
        ),
        workshop=[
            WorkshopItem(
                criterion="meta",
                status=CriterionStatus.CUMPLE,
                asked=["¿Qué quiere José esa noche?"],
                answer="Terminar el recorrido y volver a su casa.",
            ),
            WorkshopItem(
                criterion="transgresion",
                status=CriterionStatus.INTENCIONAL,
                answer="Mira el espejo aunque sabe que no tiene que hacerlo.",
            ),
            WorkshopItem(
                criterion="historia_secreta",
                status=CriterionStatus.CUMPLE,
                answer="La mujer murió en ese micro hace diez años.",
            ),
            WorkshopItem(
                criterion="inquietud",
                status=CriterionStatus.FALTA,
                question="¿Qué es lo primero raro que nota José?",
            ),
        ],
        outline=acts,
    )


def _prompts() -> dict[str, str]:
    story = _story()
    pending = [w for w in story.workshop if not w.answer]
    return {
        "consultor": WorkshopConsultant(llm=None)._prompt(story, pending),
        "planificador": OutlinePlanner(llm=None)._prompt(story),
        "verificador": OutlineVerifier(llm=None)._prompt(story, story.outline),
    }


def test_prompts_del_asistente_no_cambian():
    prompts = _prompts()
    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert prompts == json.loads(SNAPSHOT.read_text("utf-8"))


def test_el_snapshot_cubre_todas_las_secciones():
    """Si una sección deja de aparecer, el snapshot ya no la protege."""
    text = "\n".join(_prompts().values())
    for section in (
        "Estamos ayudando",
        "Tipo de horror: sobrenatural / fantasmas",
        "Cómo termina: Descansa en paz. (DECIDIDO POR EL AUTOR",
        "Personajes: José (Chofer); Marta (pasajera de todas las noches)",
        "Pregunta: «¿Qué quiere José esa noche?»",
        "(va en el acto 1)",
        "(DECIDIDO POR EL AUTOR: no se discute)",
        "- [inquietud] «¿Qué es lo primero raro que nota José?»",
        "CÓMO TIENE QUE PEGAR",
        "EFECTO QUE BUSCA EL AUTOR",
        "LO QUE EL AUTOR ESCRIBIÓ PARA CADA ACTO",
        "PROBLEMAS QUE MARCÓ LA REVISIÓN",
        "cerrar la historia con el final que decidió el autor",
        "acá el protagonista descubre o confiesa la historia secreta",
        "ACTO 1 — Ruta 36",
        "ACTO 2\n",
        "Cómo llega: Pasaron dos horas",
        "Quiere: Que el micro llegue",
        "Todavía no se cuenta: Que la mujer murió en ese asiento (se revela en el acto 4)",
        "Dice que usa:",
        "- Acto 3: Aviso ya ignorado.",
    ):
        assert section in text, section
