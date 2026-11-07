"""Spec-750 S2 (T2.5): la larga de punta a punta en el Core, con el LLM simulado.

Los mismos 5 actos que la media: el Planificador recibe cuántos hechos lleva cada acto
y las intenciones de la forma (las de la media); la Voz, las palabras de la larga.
"""

import json
import os
import re
from pathlib import Path

import httpx

from src.config import settings
from src.infrastructure.database.connection import init_db
from src.infrastructure.factories import LLMFactory
from src.main import app
from tests.integration.test_authoring_api import API
from tests.integration.test_relato_corto import _create, _generate, _sin_ids
from tests.support.recording_llm import RecordingLLM

SNAPSHOT = Path(__file__).parents[1] / "fixtures" / "snapshots" / "pipeline_prompts_larga.json"

PALABRAS = {1: (800, 950), 2: (1100, 1250), 3: (1200, 1350), 4: (1100, 1250), 5: (450, 550)}
HECHOS = {1: "5 o 6", 2: "7 u 8", 3: "8 o 9", 4: "7 u 8", 5: "3 o 4"}


async def _larga(monkeypatch, tmp_path, form: str | None = None) -> RecordingLLM:
    llm = RecordingLLM()
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'l.db'}")
    monkeypatch.setattr(LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: llm))
    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        sid = (await _create(c, structure="largo"))["story_id"]
        if form:
            state = (await c.get(f"{API}/stories/{sid}")).json()
            direction = {**state["direction"], "form": form}
            assert (await c.put(f"{API}/stories/{sid}/direction", json=direction)).status_code < 300
        await _generate(c, sid)
    return llm


async def test_prompts_del_pipeline_largo(monkeypatch, tmp_path):
    """Sin escaleta: Planificador + Verificador y 5 actos de Voz + memoria (12 llamadas)."""
    llm = await _larga(monkeypatch, tmp_path)

    roles = [call["role"] for call in llm.calls]
    assert roles == ["planificador", "verificador"] + ["voz", "journal"] * 5

    planner = llm.calls[0]["prompt"]
    assert "5 actos (unas 5.250 palabras)" in llm.calls[0]["system"] + planner
    for n, hechos in HECHOS.items():
        assert f"Lleva {hechos} hechos" in planner, n
    voces = [call["prompt"] for call in llm.calls if call["role"] == "voz"]
    for n, (low, high) in PALABRAS.items():
        assert f"entre {low} y {high} palabras" in voces[n - 1], n

    calls = [{**call, "prompt": _sin_ids(call["prompt"])} for call in llm.calls]
    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(calls, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert calls == json.loads(SNAPSHOT.read_text("utf-8"))


async def test_la_larga_recibe_las_intenciones_de_la_forma(monkeypatch, tmp_path):
    """Con una forma con actos propios, el Planificador de la larga lee los de la media."""
    from src.application.services.authoring import molde

    llm = await _larga(monkeypatch, tmp_path, form="asedio")
    planner = llm.calls[0]["prompt"]
    asedio = molde.catalogo().forma("asedio").actos["medio"]
    # El acto 5 pide «el final que decidió el autor» (la historia de prueba lo trae), como
    # en la media.
    assert "5. Desenlace (intensidad baja): cerrar la historia con el final que decidió" in planner
    for n, intencion in asedio.items():
        if n == 5:
            continue
        assert re.sub(r"\s+", " ", intencion) in re.sub(r"\s+", " ", planner), n
