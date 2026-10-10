"""Spec-650 S2: el relato corto (3 actos) de punta a punta en el Core, con el LLM simulado.

Cubre lo que la revisión del plan (§6) marcó como bugs posibles: el autoguardado no
cambia el largo (D9), cambiar el largo borra los actos y reubica las reglas (D10), una
versión del otro largo no se regenera por actos (D11), un acto fuera de la estructura
no se crea, y la estimación se separa por largo.
"""

import json
import os
import uuid
from pathlib import Path

import httpx
import pytest
import yaml

from src.application.use_cases.create_story import CreateStoryUseCase
from src.config import settings
from src.domain.exceptions import InvalidAuthoringError
from src.domain.models import TypedRule
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLGenreRepository, SQLStoryRepository
from src.infrastructure.exporters import YamlStoryExporter
from src.infrastructure.factories import LLMFactory
from src.infrastructure.loaders import YamlStoryLoader
from src.main import app
from src.presentation.runtime import job_manager
from tests.integration.test_authoring_api import API, FORM, _create, _run_job
from tests.support.recording_llm import RecordingLLM

SNAPSHOT = Path(__file__).parents[1] / "fixtures" / "snapshots" / "pipeline_prompts_corto.json"


@pytest.fixture
async def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'c.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: MockLLMAdapter())
    )
    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _generate(client, sid: str) -> dict:
    """Escribe el relato completo y devuelve el job terminado."""
    structure = (await client.get(f"{API}/stories/{sid}")).json()["structure"]
    resp = await client.post(f"/api/v1/stories/{sid}/jobs", json={})
    assert resp.status_code == 202, resp.text
    # Spec-650 T1.7: el job nace sabiendo cuántos actos escribe.
    assert resp.json()["total_beats"] == {"largo": 5, "corto": 3}[structure]
    await job_manager.wait(uuid.UUID(resp.json()["job_id"]))
    job = (await client.get(f"/api/v1/jobs/{resp.json()['job_id']}")).json()
    assert job["status"] == "done", job
    return job


async def _narrative(client, narrative_id: str) -> str:
    return (await client.get(f"/api/v1/generated-narratives/{narrative_id}")).json()["content"]


# ── Opciones y alta ──────────────────────────────────────────────────────────


async def test_las_opciones_traen_los_dos_largos(client):
    data = (await client.get(f"{API}/options")).json()
    assert [(s["id"], s["acts"]) for s in data["structures"]] == [("largo", 5), ("corto", 3)]


async def test_crear_un_corto(client):
    state = await _create(client, structure="corto")

    assert state["structure"] == "corto"
    assert [a["name"] for a in state["structure_acts"]] == [
        "Cómo empieza",
        "Qué pasa",
        "Cómo termina",
    ]
    story = (await client.get(f"/api/v1/stories/{state['story_id']}")).json()
    assert story["structure"] == "corto"
    listed = (await client.get("/api/v1/stories")).json()
    assert [s["structure"] for s in listed] == ["corto"]


async def test_sin_decir_el_largo_es_largo(client):
    state = await _create(client)
    assert state["structure"] == "largo"
    assert len(state["structure_acts"]) == 5


async def test_largo_desconocido_422(client):
    resp = await client.post(f"{API}/stories", json={**FORM, "structure": "mediano"})
    assert resp.status_code == 422


# ── El recorrido completo ────────────────────────────────────────────────────


async def test_recorrido_corto_completo(client):
    sid = (await _create(client, structure="corto"))["story_id"]
    await _run_job(client, sid, "consult")
    state = await _run_job(client, sid, "plan_outline")
    assert [a["number"] for a in state["outline"]["acts"]] == [1, 2, 3]
    state = await _run_job(client, sid, "verify_outline")
    assert [a["number"] for a in state["outline"]["acts"]] == [1, 2, 3]

    job = await _generate(client, sid)

    assert job["total_beats"] == 3
    content = await _narrative(client, job["narrative_id"])
    assert "## Acto 3" in content and "## Acto 4" not in content
    beats = (await client.get(f"/api/v1/stories/{sid}/beats")).json()
    assert [b["number"] for b in beats if b["content"]] == [1, 2, 3]

    # Regenerar un acto del corto: 2 llamadas, sigue con 3 actos.
    resp = await client.post(
        f"/api/v1/stories/{sid}/jobs",
        json={"kind": "regenerate_voz", "beat": 2, "narrative_id": job["narrative_id"]},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["total_beats"] == 3
    await job_manager.wait(uuid.UUID(resp.json()["job_id"]))
    after = (await client.get(f"/api/v1/jobs/{resp.json()['job_id']}")).json()
    assert after["status"] == "done", after
    assert "## Acto 4" not in await _narrative(client, job["narrative_id"])


async def test_generar_sin_actos_arma_tres_y_no_los_rearma(client):
    """Sin escaleta, la generación la arma con 3 actos; con 3, no la vuelve a armar."""
    sid = (await _create(client, structure="corto"))["story_id"]
    await _generate(client, sid)
    state = (await client.get(f"{API}/stories/{sid}")).json()
    assert [a["number"] for a in state["outline"]["acts"]] == [1, 2, 3]

    # Lo que la persona edita en un acto sobrevive a escribir de nuevo.
    act = state["outline"]["acts"][1]
    resp = await client.put(
        f"{API}/stories/{sid}/outline/2",
        json={**_act_form(act), "goal": "Objetivo editado por la persona"},
    )
    assert resp.status_code == 200, resp.text
    await _generate(client, sid)
    state = (await client.get(f"{API}/stories/{sid}")).json()
    assert state["outline"]["acts"][1]["goal"] == "Objetivo editado por la persona"


def _act_form(act: dict) -> dict:
    keys = (
        "goal",
        "events",
        "change_from",
        "change_to",
        "scenario",
        "on_stage",
        "held_back",
        "reveal_act",
        "seeds",
        "payoffs",
        "decisions",
        "bridge",
    )
    return {k: act[k] for k in keys if k in act} | {"rules": act.get("rules", [])}


# ── Bugs que la revisión del plan quiso evitar ───────────────────────────────


async def test_no_se_crea_un_acto_fuera_del_corto(client):
    sid = (await _create(client, structure="corto"))["story_id"]
    state = await _run_job(client, sid, "plan_outline")
    form = _act_form(state["outline"]["acts"][0])

    assert (await client.put(f"{API}/stories/{sid}/outline/4", json=form)).status_code == 404
    assert (await client.put(f"{API}/stories/{sid}/outline/3", json=form)).status_code == 200
    state = (await client.get(f"{API}/stories/{sid}")).json()
    assert [a["number"] for a in state["outline"]["acts"]] == [1, 2, 3]


async def test_el_autoguardado_de_tu_idea_no_cambia_el_largo(client):
    """D9: el formulario entero viaja en cada guardado; el largo no se pisa."""
    sid = (await _create(client, structure="corto"))["story_id"]

    resp = await client.put(
        f"{API}/stories/{sid}/direction", json={**FORM, "title": "Otra", "structure": "largo"}
    )
    assert resp.status_code == 200
    assert resp.json()["structure"] == "corto"
    resp = await client.put(f"{API}/stories/{sid}/direction", json={**FORM, "title": "Otra más"})
    assert resp.json()["structure"] == "corto"


async def test_cambiar_el_largo_borra_los_actos_y_reubica_las_reglas(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "consult")
    state = await _run_job(client, sid, "plan_outline")
    assert len(state["outline"]["acts"]) == 5
    repo = SQLStoryRepository()
    story = await repo.get_by_id(uuid.UUID(sid))
    story.typed_rules = [
        TypedRule(id="a", story_id=story.id, content="regla del 2", applies_to_beat=2),
        TypedRule(id="b", story_id=story.id, content="regla del 4", applies_to_beat=4),
        TypedRule(id="c", story_id=story.id, content="regla del 5", applies_to_beat=5),
        TypedRule(id="d", story_id=story.id, content="regla global", applies_to_beat=None),
    ]
    await repo.update_inputs(story)

    resp = await client.put(f"{API}/stories/{sid}/structure", json={"structure": "corto"})

    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["structure"] == "corto"
    assert state["outline"]["acts"] == []
    assert len(state["workshop"]["items"]) == 9  # lo respondido queda
    story = await repo.get_by_id(uuid.UUID(sid))
    assert sorted((r.content, r.applies_to_beat or 0) for r in story.typed_rules) == [
        ("regla del 2", 2),
        ("regla del 4", 3),
        ("regla del 5", 3),
        ("regla global", 0),
    ]

    # Y de vuelta a largo: 1→1, 2→3, 3→5.
    resp = await client.put(f"{API}/stories/{sid}/structure", json={"structure": "largo"})
    story = await repo.get_by_id(uuid.UUID(sid))
    assert sorted((r.content, r.applies_to_beat or 0) for r in story.typed_rules) == [
        ("regla del 2", 3),
        ("regla del 4", 5),
        ("regla del 5", 5),
        ("regla global", 0),
    ]


async def test_elegir_el_mismo_largo_no_borra_nada(client):
    sid = (await _create(client, structure="corto"))["story_id"]
    await _run_job(client, sid, "plan_outline")

    resp = await client.put(f"{API}/stories/{sid}/structure", json={"structure": "corto"})

    assert [a["number"] for a in resp.json()["outline"]["acts"]] == [1, 2, 3]


async def test_cambiar_el_largo_con_la_ia_trabajando_409(client, monkeypatch):
    sid = (await _create(client))["story_id"]
    active = type("J", (), {"id": uuid.uuid4()})()

    async def _active(_self, _story_id):
        return active

    from src.infrastructure.database.repositories import SQLJobRepository

    monkeypatch.setattr(SQLJobRepository, "get_active_for_story", _active)
    resp = await client.put(f"{API}/stories/{sid}/structure", json={"structure": "corto"})
    assert resp.status_code == 409


async def test_una_version_del_otro_largo_no_se_regenera_por_actos(client):
    """D11: la versión larga se sigue leyendo, pero regenerar el acto 2 daría una prosa
    que no encaja con los actos nuevos."""
    sid = (await _create(client))["story_id"]
    job = await _generate(client, sid)
    await client.put(f"{API}/stories/{sid}/structure", json={"structure": "corto"})
    await _generate(client, sid)  # la historia ya es corta y tiene su prosa de 3 actos

    resp = await client.post(
        f"/api/v1/stories/{sid}/jobs",
        json={"kind": "regenerate_voz", "beat": 2, "narrative_id": job["narrative_id"]},
    )

    assert resp.status_code == 409
    assert "otro largo" in resp.json()["detail"]
    assert "## Acto 5" in await _narrative(client, job["narrative_id"])  # se sigue leyendo


async def test_d11_tambien_justo_despues_de_cambiar_el_largo(client):
    """Sin escribir de nuevo, la prosa de la última generación ya no está: el aviso
    tiene que ser el de D11, no «el acto no está narrado»."""
    sid = (await _create(client))["story_id"]
    job = await _generate(client, sid)
    await client.put(f"{API}/stories/{sid}/structure", json={"structure": "corto"})

    resp = await client.post(
        f"/api/v1/stories/{sid}/jobs",
        json={"kind": "regenerate_voz", "beat": 2, "narrative_id": job["narrative_id"]},
    )

    assert resp.status_code == 409
    assert "otro largo" in resp.json()["detail"]


async def test_la_estimacion_del_corto_es_aparte(client):
    largo = (await client.get("/api/v1/jobs/estimates")).json()
    corto = (await client.get("/api/v1/jobs/estimates?structure=corto")).json()

    assert corto["full_generation"]["seconds"] < largo["full_generation"]["seconds"]
    assert corto["consult"] == largo["consult"]  # el resto no depende del largo
    sid = (await _create(client, structure="corto"))["story_id"]
    job = await _generate(client, sid)
    assert job["params"]["structure"] == "corto"


# ── YAML ─────────────────────────────────────────────────────────────────────


async def test_yaml_ida_y_vuelta_conserva_el_largo(client):
    sid = (await _create(client, structure="corto"))["story_id"]
    await _run_job(client, sid, "plan_outline")
    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))

    text = YamlStoryExporter().export(story)
    assert yaml.safe_load(text)["estructura"] == "corto"
    dto = YamlStoryLoader().load(text)
    again = await CreateStoryUseCase(SQLStoryRepository(), SQLGenreRepository()).execute(dto)

    assert again.structure == "corto"
    assert [a.number for a in again.outline] == [1, 2, 3]


async def test_yaml_de_un_largo_no_escribe_la_clave(client):
    sid = (await _create(client))["story_id"]
    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))
    assert "estructura" not in yaml.safe_load(YamlStoryExporter().export(story))


async def test_yaml_corto_con_cinco_actos_no_entra(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")
    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))
    data = yaml.safe_load(YamlStoryExporter().export(story))
    data["estructura"] = "corto"

    dto = YamlStoryLoader().load_from_dict(data)
    with pytest.raises(InvalidAuthoringError, match="3 actos"):
        await CreateStoryUseCase(SQLStoryRepository(), SQLGenreRepository()).execute(dto)


# ── Snapshot del pipeline corto ──────────────────────────────────────────────


async def test_prompts_del_pipeline_corto_no_cambian(monkeypatch, tmp_path):
    """Sin escaleta: el Planificador arma 3 actos y cada uno es Voz + memoria (8 llamadas)."""
    llm = RecordingLLM()
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'p.db'}")
    monkeypatch.setattr(LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: llm))
    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        sid = (await _create(c, structure="corto"))["story_id"]
        await _generate(c, sid)

    roles = [call["role"] for call in llm.calls]
    assert roles == ["planificador", "verificador"] + ["voz", "journal"] * 3
    calls = [{**call, "prompt": _sin_ids(call["prompt"])} for call in llm.calls]
    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAPSHOT.write_text(json.dumps(calls, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert calls == json.loads(SNAPSHOT.read_text("utf-8"))


def _sin_ids(text: str) -> str:
    import re

    return re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<id>", text)
