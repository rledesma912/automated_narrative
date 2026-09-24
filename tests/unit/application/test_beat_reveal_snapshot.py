"""Spec-450 T2.1: lo que el YAML de beats le entrega hoy a cada consumidor.

Congela, para los 5 beats, la salida que leen el Mapper (`get_by_id`), el
Resolver (`get_all`), la Voz (`assemble`) y los prompts legacy
(`format_for_beat`). Mover las reglas de revelación a `reveal_rules` (T2.2) no
debe cambiar nada de esto para una historia sin entidades.

Regenerar el snapshot (solo si el cambio de texto es intencional):
    SNAPSHOT_UPDATE=1 uv run pytest tests/unit/application/test_beat_reveal_snapshot.py
"""

import json
import os
from pathlib import Path

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.narrative_context_assembler import NarrativeContextAssembler
from src.domain.models import MacroBeat, NarrativeJournal

SNAPSHOT = Path(__file__).parents[2] / "fixtures" / "snapshots" / "beat_reveal.json"

# Claves del beat que leen los consumidores (PromptBuilder, resolver, mapper).
_KEYS = (
    "id",
    "name",
    "intent",
    "intensity",
    "must",
    "must_not",
    "state_change",
    "success_signal",
    "word_limit",
)


def _project(beat: dict) -> dict:
    return {k: beat[k] for k in _KEYS if k in beat}


def capture() -> dict:
    repo = BeatSpecRepository()
    assembler = NarrativeContextAssembler(repo)
    journal = NarrativeJournal(
        last_events="Rosa cerró el galpón.",
        unresolved_mysteries="¿Quién silbaba?",
        physical_emotional_state="Cansada",
    )
    out: dict = {"get_all": [_project(b) for b in repo.get_all()]}
    for n in range(1, repo.num_beats + 1):
        beat = MacroBeat(
            number=n,
            summary=f"Rosa hace algo en el acto {n}.",
            active_scenario_id="S1",
        )
        out[f"beat_{n}"] = {
            "get_by_id": _project(repo.get_by_id(n)),
            "compact": repo.format_for_beat(n, "compact"),
            "frontier": repo.format_for_beat(n, "frontier"),
            "assemble": assembler.assemble(
                beat,
                {"resonance": "La grieta.", "label_voz": "LA GRIETA"},
                journal if n > 1 else None,
                cast_block="PERSONAJES:\n- Rosa",
                active_rules=["Nadie entra de noche"],
            ),
        }
    return out


def test_salida_de_los_beats_sin_entidades_no_cambia():
    current = capture()
    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert current == json.loads(SNAPSHOT.read_text("utf-8"))
