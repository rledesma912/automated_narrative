"""Spec-680 C1: cómo habla quien narra.

El habla de la historia reemplaza al «español rioplatense» fijo en la Voz, la Memoria y
el Planificador; las pantallas y lo que lee quien arma la historia (Consultor,
Verificador) siguen en voseo. El snapshot `voice_prompts_mexicano.json` es la Voz de
`test_voice_prompts_snapshot` con habla mexicana.

    SNAPSHOT_UPDATE=1 uv run pytest tests/unit/application/authoring/test_hablas.py
"""

import json
import os
import re
from pathlib import Path

import pytest

from src.application.services.authoring import catalog
from src.application.services.authoring.outline_narrator import OutlineNarrator
from src.application.services.authoring.planner import OutlinePlanner
from src.domain.models import Direction, Story
from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter
from tests.unit.application.authoring.test_voice_prompts_snapshot import _memory, _story

SNAPSHOT = Path(__file__).parents[3] / "fixtures" / "snapshots" / "voice_prompts_mexicano.json"
PROMPTS = Path(__file__).parents[4] / "config" / "prompts_generation"


def _con_habla(habla: str) -> Story:
    story = _story()
    return story.model_copy(
        update={"direction": story.direction.model_copy(update={"habla": habla})}
    )


class _Grabador(MockLLMAdapter):
    """El mock, guardando el system prompt de cada llamada."""

    def __init__(self):
        super().__init__()
        self.systems: list[str] = []

    async def generate(self, prompt, *, system_prompt=None, **kw):
        self.systems.append(system_prompt or "")
        return await super().generate(prompt, system_prompt=system_prompt, **kw)


# ── Catálogo ─────────────────────────────────────────────────────────────────


def test_la_de_siempre_es_la_primera_y_sin_extras():
    hablas = catalog.hablas()
    assert [h.id for h in hablas] == ["rioplatense", "mexicano", "neutro", "espana"]
    assert hablas[0].prompt == "español rioplatense"
    assert hablas[0].voz == "" and hablas[0].ajenas == ()
    assert all(h.voz and h.ajenas for h in hablas[1:])


@pytest.mark.parametrize("habla", ["", "klingon"])
def test_sin_habla_o_una_que_no_existe_es_la_de_siempre(habla):
    assert catalog.habla_de(_con_habla(habla)).id == "rioplatense"
    sin_direccion = _story().model_copy(update={"direction": None})
    assert catalog.habla_de(sin_direccion).id == "rioplatense"


def test_las_ajenas_marcan_el_voseo_y_no_lo_comun():
    mexicano = [re.compile(p, re.I) for p in catalog.habla("mexicano").ajenas]
    hits = lambda t: [m.group(0) for p in mexicano for m in p.finditer(t)]  # noqa: E731
    # Lo que se coló en la medición «antes» (§7, S0).
    assert hits("saben a qué hora abrís la cortina y qué comprás") == ["abrís", "comprás"]
    assert hits("una risa media nerviosa por la plata") == ["la plata", "media nerviosa"]
    # Palabras con tilde final que no son voseo, y el «tú» de siempre.
    assert hits("después estás más atrás; además nomás un país; ¿vas?") == []


# ── Prompts ──────────────────────────────────────────────────────────────────


def test_con_rioplatense_la_voz_dice_lo_de_siempre():
    system, _ = OutlineNarrator(llm=None).voice_prompts(_story(), _story().outline[0], None)
    assert "prosa narrativa en español rioplatense." in system
    assert (
        "palabras que existan en el español rioplatense; si dudás de una palabra, elegí una más simple.\n- Nombrá"
        in system
    )


def test_con_mexicano_la_voz_no_dice_rioplatense():
    story = _con_habla("mexicano")
    system, user = OutlineNarrator(llm=None).voice_prompts(story, story.outline[0], None)
    assert "prosa narrativa en español de México." in system
    assert "palabras que existan en el español de México" in system
    assert catalog.habla("mexicano").voz in system
    assert "rioplatense" not in system + user


async def test_la_memoria_escribe_en_el_habla_de_la_historia():
    story = _con_habla("mexicano")
    llm = _Grabador()
    await OutlineNarrator(llm=llm).remember(story, story.outline[0], "Texto del acto.", None)
    assert llm.systems[0].count("Español de México, frases cortas.") == 1


def test_el_planificador_escribe_los_hechos_en_el_habla():
    planner = OutlinePlanner(llm=None)
    assert "Español rioplatense, frases simples." in planner.system_prompt(_story())
    mexicano = planner.system_prompt(_con_habla("mexicano"))
    assert "Español de México, frases simples." in mexicano
    assert "rioplatense" not in mexicano


def test_quien_arma_la_historia_sigue_leyendo_voseo():
    """El Consultor, el Verificador y la IA que sugiere la forma le hablan a la persona."""
    for name in (
        "authoring_consultant_system",
        "authoring_verifier_system",
        "authoring_form_system",
    ):
        text = (PROMPTS / f"{name}.md").read_text("utf-8")
        assert "{habla}" not in text and "Voseo rioplatense" in text


def test_direction_guarda_el_habla():
    assert Direction(habla="mexicano").habla == "mexicano"
    assert Direction().habla == ""


# ── Snapshot ─────────────────────────────────────────────────────────────────


def _prompts() -> list[dict[str, str]]:
    story = _con_habla("mexicano")
    narrator = OutlineNarrator(llm=None)
    out = []
    for act in story.outline:
        previous = "El micro siguió por la ruta. Nadie subió." if act.number > 1 else ""
        system, user = narrator.voice_prompts(story, act, _memory(act.number), previous)
        out.append({"acto": act.number, "system": system, "user": user})
    return out


def test_prompts_de_la_voz_mexicana_no_cambian():
    prompts = _prompts()
    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert prompts == json.loads(SNAPSHOT.read_text("utf-8"))
