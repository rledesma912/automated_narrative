"""Snapshot de los prompts de la Voz con todas sus secciones (Spec-620).

El snapshot del pipeline usa una historia sin amenaza, sin elenco con parentescos y sin
final decidido: no protege esas secciones. Este arma los prompts de los 5 actos
directamente con una historia que las activa todas (dos amenazas con niveles distintos,
personajes con y sin rol, final del autor, un acto sin escenario).

Para regenerarlo a propósito:
    SNAPSHOT_UPDATE=1 uv run pytest tests/unit/application/authoring/test_voice_prompts_snapshot.py
"""

import json
import os
import uuid
from pathlib import Path

from src.application.services.authoring.outline_narrator import OutlineNarrator
from src.domain.models import (
    ActOutline,
    Direction,
    Entity,
    NarrativeJournal,
    RevealLevel,
    Story,
    TypedRule,
)

SNAPSHOT = Path(__file__).parents[3] / "fixtures" / "snapshots" / "voice_prompts.json"
STORY_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def _story() -> Story:
    acts = [
        ActOutline(
            number=n,
            bridge="" if n == 1 else f"Pasó media hora desde el acto {n - 1}.",
            goal=f"Llegar a la terminal (acto {n})",
            events=[f"José oye un golpe en el acto {n}.", "Marta le habla desde el fondo."],
            change_to=f"José ya no está tranquilo (acto {n})",
            scenario="Ruta 36" if n != 4 else "",
            on_stage=["José", "Marta", "El inspector"],
            held_back="Que Marta murió en ese asiento" if n == 2 else "",
        )
        for n in range(1, 6)
    ]
    return Story(
        id=STORY_ID,
        title="la pena del colectivo",
        protagonista="José: chofer de micros",
        relator="Primera persona. Narrador: José.",
        sinopsis="José ve por el espejo a una mujer que murió en su micro. Después la busca.",
        narrator_config={"storyteller_name": "José"},
        personajes_full=[
            {"name": "José", "role": "Chofer"},
            {"name": "Marta", "role": "Pasajera muerta, conocida de José"},
            {"name": "El inspector"},
        ],
        typed_rules=[
            TypedRule(
                id="r1",
                story_id=STORY_ID,
                content="El micro nunca se detiene en el puente.",
                applies_to_beat=3,
            )
        ],
        entities=[
            Entity(
                story_id=STORY_ID,
                order_index=0,
                name="La pasajera",
                nature_id="espectro",
                description="Una mujer que murió en el micro.",
                manifestations="olor a jazmín; frío en la nuca; reflejo en el espejo",
                limits="No puede bajar del micro.",
                reveal_level=RevealLevel.PROGRESIVA,
            ),
            Entity(
                story_id=STORY_ID,
                order_index=1,
                nature_id="desconocida",
                manifestations="golpes en el techo",
                reveal_level=RevealLevel.NUNCA,
            ),
        ],
        direction=Direction(
            premise="José ve por el espejo a una mujer que murió en su micro. Después la busca.",
            effect="pavor",
            ending="Descansa en paz.",
            ending_intentional=True,
            telling="caso",
        ),
        outline=acts,
    )


def _memory(n: int) -> NarrativeJournal | None:
    if n == 1:
        return None
    return NarrativeJournal(
        last_events="Acto 1: José arrancó el recorrido.",
        physical_emotional_state="Asustado, con las manos frías.",
        used_motifs=["olor a jazmín", "un silencio raro"],
        body_state="Un raspón en la mano izquierda.",
        narrator_traits=["toma mate mientras maneja"],
    )


def _prompts() -> list[dict[str, str]]:
    story = _story()
    narrator = OutlineNarrator(llm=None)
    out = []
    for act in story.outline:
        previous = (
            "Primer párrafo.\n\nEl micro siguió por la ruta. Nadie subió." if act.number > 1 else ""
        )
        system, user = narrator.voice_prompts(story, act, _memory(act.number), previous)
        out.append({"acto": act.number, "system": system, "user": user})
    return out


def test_prompts_de_la_voz_no_cambian():
    prompts = _prompts()
    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert prompts == json.loads(SNAPSHOT.read_text("utf-8"))


def test_el_snapshot_cubre_todas_las_secciones():
    """Si una sección deja de aparecer, el snapshot ya no la protege."""
    text = "\n".join(p["system"] + p["user"] for p in _prompts())
    for section in (
        "Sos José y contás en primera persona",
        "CÓMO LLAMÁS A CADA PERSONAJE (sos José)",
        "- El inspector: sin rol",
        "LA HISTORIA, PARA QUE CONOZCAS A JOSÉ",
        "CÓMO SE LLEGA A ESTE ACTO",
        "ASÍ TERMINÓ EL ACTO ANTERIOR",
        "LO QUE QUIERE JOSÉ EN ESTE ACTO",
        "REGLAS DE ESTE ACTO",
        "AL TERMINAR EL ACTO",
        "NO REVELES TODAVÍA",
        "AMENAZA EN ESTE ACTO",
        "Presencia 2",
        "  Cómo se percibe:",
        "  Cómo mostrarla:",
        "(no se indica)",
        "cerrar la historia con el final que decidió el autor: Descansa en paz.",
        "CÓMO ESTÁ JOSÉ AHORA",
        "ASÍ ES JOSÉ",
        "Acto 1: José oye un golpe",
        "· Exposición",
        "· Desenlace",
        # Spec-640: el registro de anécdota y las muletillas que marcó la usuaria.
        "CONTALO COMO UNA ANÉCDOTA",
        "Como mucho una comparación por acto",
        "pasó lo peor",
    ):
        assert section in text, section


def test_el_comienzo_libre_va_solo_en_el_acto_1():
    """Spec-650 (prueba de las usuarias): todos los relatos arrancaban con «Mirá».

    La opción «Como un caso entre amigos» traía «mirá» de ejemplo y la Voz lo ponía en la
    primera palabra. En el acto 1 la Voz elige por dónde entrar, sin muletillas.
    """
    prompts = _prompts()
    assert "CÓMO EMPEZAR" in prompts[0]["user"]
    assert all("CÓMO EMPEZAR" not in p["user"] for p in prompts[1:])
    assert all("«mirá»" not in p["system"].lower() for p in prompts)
