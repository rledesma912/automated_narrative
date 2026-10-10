"""Snapshots de los prompts del relato corto (Spec-650): la Voz y el asistente.

Las mismas historias que los snapshots del largo (`test_voice_prompts_snapshot.py`,
`test_assistant_prompts_snapshot.py`), pasadas a la estructura corta: 3 actos, la regla
y lo que se revela dentro de esos actos. Los del largo no cambian (Spec-650 D8).

Para regenerarlos a propósito:
    SNAPSHOT_UPDATE=1 uv run pytest tests/unit/application/authoring/test_prompts_corto_snapshot.py
"""

import json
import os
from pathlib import Path

from src.application.services.authoring.consultant import WorkshopConsultant
from src.application.services.authoring.outline_narrator import OutlineNarrator
from src.application.services.authoring.planner import OutlinePlanner
from src.application.services.authoring.verifier import OutlineVerifier
from src.domain.models import Story
from tests.unit.application.authoring import (
    test_assistant_prompts_snapshot as asistente,
)
from tests.unit.application.authoring import (
    test_voice_prompts_snapshot as voz,
)

SNAPSHOTS = Path(__file__).parents[3] / "fixtures" / "snapshots"


def _corto(story: Story) -> Story:
    """La historia en 3 actos: lo que estaba en los actos 4 y 5 se va o se reubica."""
    outline = [a for a in story.outline if a.number <= 3]
    outline = [a.model_copy(update={"reveal_act": 3}) if a.reveal_act > 3 else a for a in outline]
    rules = [
        r.model_copy(update={"applies_to_beat": 2})
        if r.applies_to_beat and r.applies_to_beat > 2
        else r
        for r in story.typed_rules
    ]
    return story.model_copy(update={"structure": "corto", "outline": outline, "typed_rules": rules})


def _voice_prompts() -> list[dict[str, str]]:
    story = _corto(voz._story())
    narrator = OutlineNarrator(llm=None)
    out = []
    for act in story.outline:
        previous = (
            "Primer párrafo.\n\nEl micro siguió por la ruta. Nadie subió." if act.number > 1 else ""
        )
        system, user = narrator.voice_prompts(story, act, voz._memory(act.number), previous)
        out.append({"acto": act.number, "system": system, "user": user})
    return out


def _assistant_prompts() -> dict[str, str]:
    story = _corto(asistente._story())
    pending = [w for w in story.workshop if not w.answer]
    planner = OutlinePlanner(llm=None)
    return {
        "consultor": WorkshopConsultant(llm=None)._prompt(story, pending),
        "planificador_system": planner.templates.load("authoring_planner_system.md").format(
            num_actos=3
        ),
        "planificador": planner._prompt(story),
        "verificador": OutlineVerifier(llm=None)._prompt(story, story.outline),
    }


def _check(name: str, data) -> None:
    path = SNAPSHOTS / name
    if os.environ.get("SNAPSHOT_UPDATE"):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert data == json.loads(path.read_text("utf-8"))


def test_prompts_de_la_voz_corto_no_cambian():
    _check("voice_prompts_corto.json", _voice_prompts())


def test_prompts_del_asistente_corto_no_cambian():
    _check("assistant_prompts_corto.json", _assistant_prompts())


def test_la_voz_del_corto_recibe_sus_actos_y_sus_palabras():
    prompts = {p["acto"]: p["user"] for p in _voice_prompts()}
    assert sorted(prompts) == [1, 2, 3]
    for n, user in prompts.items():
        assert user.startswith(f"ACTO {n} DE 3 ·"), user[:40]
        assert "de 5" not in user.lower()
    assert "· Inicio" in prompts[1] and "240" in prompts[1] and "290" in prompts[1]
    assert "· Nudo" in prompts[2] and "450" in prompts[2] and "520" in prompts[2]
    assert "· Desenlace" in prompts[3] and "190" in prompts[3] and "240" in prompts[3]
    # El final del autor va en el último acto del corto (el 3), no en el 5.
    assert "cerrar la historia con el final que decidió el autor" in prompts[3]
    assert "cerrar la historia con el final que decidió el autor" not in prompts[2]
    # La regla reubicada al nudo llega ahí.
    assert "El micro nunca se detiene en el puente." in prompts[2]
    # La amenaza con la exposición del corto: en el nudo ya hay presencia directa.
    assert "Presencia directa" in prompts[2]


def test_el_asistente_del_corto_habla_de_tres_actos():
    p = _assistant_prompts()
    text = "\n".join(p.values())
    assert "en 3 actos" in p["planificador_system"]
    assert "en 3 actos (unas 1.050 palabras)" in p["consultor"]
    for fixed in ("5 actos", "1 a 5", "de 3 a 5 hechos", "acto 5", "acto 4"):
        assert fixed not in text.lower(), fixed
    assert "LOS 3 ACTOS:" in p["planificador"]
    assert '"numero": 1 a 3.' in p["planificador"]
    for line in ("1. Inicio (intensidad baja)", "2. Nudo (intensidad alta)", "3. Desenlace"):
        assert line in p["planificador"], line
    assert "4. " not in p["planificador"].split("ACTOS")[-1][:400]
    # Cuántos hechos por acto (la extensión sale de ahí).
    assert "Lleva 4 o 5 hechos, no más" in p["planificador"]
    assert "ni uno más" in p["planificador"]
    # La historia secreta se revela en el nudo (revela_secreto: 2) y el final, en el 3.
    nudo = next(line for line in p["planificador"].splitlines() if line.startswith("2. Nudo"))
    assert "historia secreta" in nudo
    final = next(line for line in p["planificador"].splitlines() if line.startswith("3. Desenlace"))
    assert "final que decidió el autor" in final
    # Receta del efecto del corto y acto de la decisión según el corto.
    assert "al final del acto 2" in p["planificador"]
    assert '("" en el acto 3)' in p["planificador"]
    assert "(va en el acto 2)" in p["planificador"]  # transgresión: acto 2 en los dos
