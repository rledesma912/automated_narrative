"""Spec-530 S3: API del asistente de autoría (con el LLM simulado)."""

import asyncio
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.main import app
from src.presentation import authoring_jobs
from src.presentation.runtime import job_manager

API = "/api/v1/authoring"
FORM = {
    "title": "La pena del colectivo",
    "genero": "",
    "subgenero": "",
    "premise": "José ve por el espejo a una mujer que murió en su micro.",
    "effect": "pavor",
    "ending": "Descansa en paz.",
    "ending_intentional": True,
    "telling": "caso",
    "protagonist_name": "José",
    "protagonist_role": "Chofer de micros",
    "narrator": "",
}


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'a.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: MockLLMAdapter())
    )
    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _create(client, **extra) -> dict:
    resp = await client.post(f"{API}/stories", json={**FORM, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _run_job(client, story_id: str, kind: str) -> dict:
    resp = await client.post(f"/api/v1/stories/{story_id}/jobs", json={"kind": kind})
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert job["status"] == "done", job
    return (await client.get(f"{API}/stories/{story_id}")).json()


async def test_opciones(client):
    data = (await client.get(f"{API}/options")).json()
    assert [e["id"] for e in data["effects"]][:2] == ["pavor", "susto"]
    assert data["criteria"][0]["nombre"] == "Qué quiere el protagonista"


async def test_crear_desde_la_direccion(client):
    state = await _create(client)

    assert state["direction"] == FORM | {"narrator": "José", "effect_other": "", "threat": None}
    assert state["workshop"]["finish"]["kind"] == "sin_analizar"
    assert state["characters"] == [{"name": "José", "kind": "persona", "relation": "", "acts": []}]
    story = (await client.get(f"/api/v1/stories/{state['story_id']}")).json()
    assert story["protagonista"] == "José: Chofer de micros"
    assert story["sinopsis"] == FORM["premise"]


async def test_genero_invalido_422(client):
    resp = await client.post(f"{API}/stories", json={**FORM, "genero": "inventado"})
    assert resp.status_code == 422


async def test_guardar_la_direccion_no_toca_el_taller_ni_la_escaleta(client):
    state = await _create(client)
    sid = state["story_id"]
    await _run_job(client, sid, "consult")
    await _run_job(client, sid, "plan_outline")

    resp = await client.put(f"{API}/stories/{sid}/direction", json={**FORM, "title": "Otra"})

    after = resp.json()
    assert resp.status_code == 200
    assert after["direction"]["title"] == "Otra"
    assert len(after["workshop"]["items"]) == 9
    assert len(after["outline"]["acts"]) == 5


async def test_taller_con_la_ia(client):
    sid = (await _create(client))["story_id"]

    state = await _run_job(client, sid, "consult")

    items = {w["criterion"]: w for w in state["workshop"]["items"]}
    assert items["final"]["status"] == "intencional"  # no se evalúa
    assert items["meta"]["question"] == "¿Pregunta de ejemplo sobre meta?"
    assert len(items["meta"]["options"]) == 3
    assert items["meta"]["nombre"] == "Qué quiere José" and items["meta"]["por_que"]
    assert state["workshop"]["round"] == 1
    assert state["workshop"]["finish"]["kind"] == "abierto"


async def test_taller_sin_de_que_trata_422(client):
    sid = (await _create(client, premise=""))["story_id"]
    resp = await client.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "consult"})
    assert resp.status_code == 422


async def test_acciones_del_taller(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "consult")

    async def act(criterion, **body):
        resp = await client.patch(f"{API}/stories/{sid}/workshop/{criterion}", json=body)
        return resp

    state = (await act("meta", action="answer", text="Llegar a casa")).json()
    state = (await act("en_juego", action="decide")).json()
    state = (await act("vulnerabilidad", action="intentional", text="Así")).json()
    items = {w["criterion"]: w for w in state["workshop"]["items"]}
    assert (items["meta"]["status"], items["meta"]["answer"], items["meta"]["question"]) == (
        "cumple",
        "Llegar a casa",
        "",
    )
    assert items["en_juego"]["answer"] == "Primera opción (en_juego)"
    assert items["vulnerabilidad"]["status"] == "intencional"
    assert [d["id"] for d in state["outline"]["decisions"]] == [
        "meta",
        "en_juego",
        "vulnerabilidad",
        "final",
    ]

    state = (await act("vulnerabilidad", action="reopen")).json()
    assert (
        next(w for w in state["workshop"]["items"] if w["criterion"] == "vulnerabilidad")["status"]
        == "falta"
    )
    assert (await act("inventado", action="decide")).status_code == 404
    assert (await act("meta", action="answer", text="  ")).status_code == 422


async def test_escaleta_y_revision(client):
    sid = (await _create(client))["story_id"]
    assert (
        await client.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "verify_outline"})
    ).status_code == 422

    state = await _run_job(client, sid, "plan_outline")

    acts = state["outline"]["acts"]
    assert [a["number"] for a in acts] == [1, 2, 3, 4, 5]
    assert [w["text"] for w in acts[1]["warnings"]] == [
        "El encuentro del acto 2 repite el del acto 1."
    ]
    assert acts[1]["warnings"][0]["source"] == "ia" and not acts[1]["warnings"][0]["dismissed"]
    assert "Escenario de ejemplo" in [s["name"] for s in state["scenarios"]]
    state = await _run_job(client, sid, "verify_outline")
    assert state["outline"]["acts"][1]["warnings"]


async def test_editar_un_acto(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")

    resp = await client.put(
        f"{API}/stories/{sid}/outline/2",
        json={"goal": "  Huir ", "events": ["Frena", " ", "Baja"], "scenario": "La ruta"},
    )

    act = resp.json()["outline"]["acts"][1]
    assert (act["goal"], act["events"], act["scenario"]) == ("Huir", ["Frena", "Baja"], "La ruta")
    assert act["warnings"]  # quedan hasta revisar de nuevo
    assert (await client.put(f"{API}/stories/{sid}/outline/6", json={})).status_code == 404


async def test_con_la_ia_trabajando_no_se_puede_guardar(client, monkeypatch):
    sid = (await _create(client))["story_id"]
    block = asyncio.Event()

    def _runner(_story_id):
        def _run():
            async def _gen():
                await block.wait()
                yield StreamEvent(event=StreamEventType.DONE, data={})

            return _gen()

        return _run

    monkeypatch.setitem(authoring_jobs._RUNNERS, authoring_jobs.JobKind.CONSULT, _runner)
    job = (await client.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "consult"})).json()

    state = (await client.get(f"{API}/stories/{sid}")).json()
    assert state["active_job"]["kind"] == "consult"
    assert (await client.put(f"{API}/stories/{sid}/direction", json=FORM)).status_code == 409
    resp = await client.patch(f"{API}/stories/{sid}/workshop/meta", json={"action": "decide"})
    assert resp.status_code == 409 and resp.headers["x-job-id"] == job["job_id"]
    # Spec-630 S3: lo nuevo de «Los actos» también espera a la IA.
    for path, body in [
        ("outline/1/warnings/resolve", {"key": "x"}),
        ("characters/remove", {"name": "José"}),
        ("scenarios", {"name": "El galpón"}),
        ("scenarios/remove", {"name": "El galpón"}),
    ]:
        assert (await client.post(f"{API}/stories/{sid}/{path}", json=body)).status_code == 409
    block.set()
    await job_manager.wait(uuid.UUID(job["job_id"]))


async def test_estimaciones_de_los_jobs_nuevos(client):
    data = (await client.get("/api/v1/jobs/estimates")).json()
    assert {"consult", "plan_outline", "verify_outline"} <= data.keys()


async def test_reglas_personajes_y_avisos_desde_la_escaleta(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")

    state = (
        await client.put(
            f"{API}/stories/{sid}/outline/2",
            json={"events": ["Frena"], "rules": ["Solo aparece si está solo", " "]},
        )
    ).json()
    assert state["outline"]["acts"][1]["rules"] == ["Solo aparece si está solo"]
    assert state["outline"]["acts"][2]["rules"] == []
    rules = (await client.get(f"/api/v1/stories/{sid}")).json()["storyteller_config"]["rules"]
    assert [(r["text"], r.get("applies_to_beat")) for r in rules] == [
        ("Solo aparece si está solo", 2)
    ]

    state = (
        await client.post(
            f"{API}/stories/{sid}/characters",
            json={"name": "El sereno", "kind": "sin_nombre", "relation": "Lo conozco de vista"},
        )
    ).json()
    await client.post(f"{API}/stories/{sid}/characters", json={"name": "el sereno"})  # no duplica
    state = (await client.get(f"{API}/stories/{sid}")).json()
    assert [c["name"] for c in state["characters"]] == ["José", "El sereno"]

    warning = state["outline"]["acts"][1]["warnings"][0]
    state = (
        await client.post(
            f"{API}/stories/{sid}/outline/2/warnings/dismiss", json={"key": warning["key"]}
        )
    ).json()
    assert [w["dismissed"] for w in state["outline"]["acts"][1]["warnings"]] == [True]

    # Spec-550 H10: revisar de nuevo no lo trae de vuelta (el mock repite el mismo aviso).
    state = await _run_job(client, sid, "verify_outline")
    visibles = [w for w in state["outline"]["acts"][1]["warnings"] if not w["dismissed"]]
    assert warning["text"] not in [w["text"] for w in visibles]

    # «Volver a mostrar».
    state = (
        await client.post(
            f"{API}/stories/{sid}/outline/2/warnings/restore", json={"key": warning["key"]}
        )
    ).json()
    assert any(
        w["key"] == warning["key"] and not w["dismissed"]
        for w in state["outline"]["acts"][1]["warnings"]
    )
    assert (
        await client.post(f"{API}/stories/{sid}/outline/2/warnings/dismiss", json={"key": "x"})
    ).status_code == 404

    # Rearmar la escaleta olvida lo ignorado (actos nuevos).
    await client.post(
        f"{API}/stories/{sid}/outline/2/warnings/dismiss", json={"key": warning["key"]}
    )
    state = await _run_job(client, sid, "plan_outline")
    assert not any(w["dismissed"] for a in state["outline"]["acts"] for w in a["warnings"])


async def test_la_amenaza_desde_la_direccion(client):
    threat = {
        "name": "La mujer del asiento 32",
        "nature": "espiritu",
        "description": "Quiere que José se detenga.",
        "manifestations": "Olor a flores",
        "limits": "Solo cuando está solo",
        "reveal_level": "progresiva",
    }
    form = {**FORM, "genero": "paranormal", "subgenero": "fantasmas", "threat": threat}
    state = await _create(
        client, **{k: v for k, v in form.items() if k not in FORM or FORM[k] != v}
    )
    assert state["direction"]["threat"] == threat

    sid = state["story_id"]
    bad = {**form, "threat": {**threat, "nature": "inexistente"}}
    assert (await client.put(f"{API}/stories/{sid}/direction", json=bad)).status_code == 422
    state = (
        await client.put(f"{API}/stories/{sid}/direction", json={**form, "threat": None})
    ).json()
    assert state["direction"]["threat"] is None


async def test_generar_con_escaleta_usa_la_escaleta(client, monkeypatch):
    """Spec-530 S5: sin Analyst ni Mapper; la Voz recibe los hechos del acto."""
    roles: list[str] = []

    class RecordingMock(MockLLMAdapter):
        async def generate(self, prompt, *, role=None, **kwargs):
            roles.append(role)
            return await super().generate(prompt, role=role, **kwargs)

    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")
    monkeypatch.setattr(LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: RecordingMock()))

    resp = await client.post(f"/api/v1/stories/{sid}/jobs", json={})
    job_id = resp.json()["job_id"]
    await job_manager.wait(uuid.UUID(job_id))
    job = (await client.get(f"/api/v1/jobs/{job_id}")).json()

    assert job["status"] == "done" and job["narrative_id"]
    assert roles == ["voz", "journal"] * 5
    beats = (await client.get(f"/api/v1/stories/{sid}/beats")).json()
    assert [b["number"] for b in beats] == [1, 2, 3, 4, 5]
    from src.infrastructure.database.repositories import SQLStoryRepository

    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))
    assert story.outline and len(story.outline) == 5  # la escaleta sobrevive a generar
    journal = await SQLStoryRepository().get_journal(uuid.UUID(sid))
    assert journal.used_motifs == ["un motivo de ejemplo"]
    # Spec-590: el cuerpo y los rasgos de quien narra se guardan y se leen de la DB.
    assert journal.body_state == "Un raspón en la mano izquierda."
    assert journal.narrator_traits == ["toma mate amargo"]
    assert journal.last_events.startswith("Acto 1: Pasó lo del acto.")
    assert (
        "Hecho 3.1 de ejemplo" in story.outline[2].events[0]
    )  # Spec-570: la entrada vive en la escaleta


async def test_control_de_repeticion_del_relato(client):
    from src.domain.models import GeneratedNarrative
    from src.infrastructure.database.repositories import SQLGeneratedNarrativeRepository

    sid = (await _create(client))["story_id"]
    narrative = GeneratedNarrative(
        story_template_id=uuid.UUID(sid),
        title="R",
        content="## Acto 1\n\nEl olor dulce y putrefacto me llenó la nariz.\n\n"
        "## Acto 2\n\nOtra vez el olor dulce y putrefacto. Se me heló la sangre.",
    )
    await SQLGeneratedNarrativeRepository().save(narrative)

    data = (await client.get(f"/api/v1/generated-narratives/{narrative.id}/repetition")).json()

    assert data["acts"][0] == {
        "number": 1,
        "repeated": [],
        "cliches": [],
        "invented_names": [],
        "cut_sentences": [],
        "cut_count": 0,
        "cut_pct": 0,
        "too_cut": False,
        "dialogue": 0,
    }
    assert data["acts"][1]["repeated"] == ["«el olor dulce y putrefacto» (del acto 1)"]
    assert data["acts"][1]["cliches"] == ["me heló la sangre"]  # una vez, aunque haya variantes
    # Spec-590 F: «Otra vez el olor dulce y putrefacto.» no tiene verbo (1 de 2 oraciones).
    assert data["acts"][1]["cut_sentences"] == ["Otra vez el olor dulce y putrefacto."]
    assert (data["acts"][1]["cut_pct"], data["acts"][1]["too_cut"]) == (50, True)
    assert data["acts"][1]["dialogue"] == 0


async def test_una_historia_con_sinopsis_larga_se_lee_y_se_guarda(client):
    sid = (await _create(client, premise="x" * 5000))["story_id"]
    assert (await client.get(f"{API}/stories/{sid}")).status_code == 200
    resp = await client.put(f"{API}/stories/{sid}/direction", json={**FORM, "premise": "y" * 5500})
    assert resp.status_code == 200
    assert (
        await client.put(f"{API}/stories/{sid}/direction", json={**FORM, "premise": "z" * 7000})
    ).status_code == 422


async def test_una_historia_importada_se_abre_en_el_asistente(client):
    """Spec-530 S7: sin wizard, las historias sin dirección se editan en el asistente."""
    payload = {
        "title": "Importada",
        "protagonista": "Irene: narradora",
        "relator": "Primera persona",
        "sinopsis": "Irene cruza el monte de noche.",
        "escenarios": "El monte",
        "personajes_full": [{"id": "P1", "name": "Irene", "role": "Narradora"}],
    }
    sid = (await client.post("/api/v1/stories?action=save", json=payload)).json()["id"]

    state = (await client.get(f"{API}/stories/{sid}")).json()

    assert state["direction"]["premise"] == "Irene cruza el monte de noche."
    assert state["direction"]["protagonist_name"] == "Irene"
    assert state["workshop"]["finish"]["kind"] == "sin_analizar"


# ── Spec-630 S3: personajes, lugares y avisos desde «Los actos» ──────────────


async def test_resolver_un_aviso_lo_quita(client):
    sid = (await _create(client))["story_id"]
    state = await _run_job(client, sid, "plan_outline")
    warning = state["outline"]["acts"][1]["warnings"][0]

    state = (
        await client.post(
            f"{API}/stories/{sid}/outline/2/warnings/resolve", json={"key": warning["key"]}
        )
    ).json()
    # B2: no queda ni visible ni ignorado.
    assert warning["key"] not in [w["key"] for w in state["outline"]["acts"][1]["warnings"]]
    resp = await client.post(f"{API}/stories/{sid}/outline/2/warnings/resolve", json={"key": "x"})
    assert resp.status_code == 404
    resp = await client.post(f"{API}/stories/{sid}/outline/6/warnings/resolve", json={"key": "x"})
    assert resp.status_code == 404


async def test_sumar_personaje_lo_marca_en_el_acto(client):
    sid = (await _create(client))["story_id"]
    before = await _run_job(client, sid, "plan_outline")

    state = (
        await client.post(
            f"{API}/stories/{sid}/characters",
            json={"name": "Tío  Rubén", "kind": "persona", "act": 2},
        )
    ).json()
    acts = state["outline"]["acts"]
    assert "Tío Rubén" in acts[1]["on_stage"]
    for n in (0, 2, 3, 4):
        assert acts[n]["on_stage"] == before["outline"]["acts"][n]["on_stage"]
    rub = next(c for c in state["characters"] if c["name"] == "Tío Rubén")
    assert rub["kind"] == "persona" and rub["acts"] == [2]

    # Ya existe: no se duplica; con otro acto, se marca también ahí (con su nombre de siempre).
    state = (
        await client.post(f"{API}/stories/{sid}/characters", json={"name": "tío rubén", "act": 4})
    ).json()
    assert [c["name"] for c in state["characters"]].count("Tío Rubén") == 1
    assert "Tío Rubén" in state["outline"]["acts"][3]["on_stage"]
    assert (
        await client.post(f"{API}/stories/{sid}/characters", json={"name": "X", "act": 6})
    ).status_code == 422


async def test_borrar_personaje_lo_saca_de_los_actos(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")
    for act in (1, 3):
        await client.post(f"{API}/stories/{sid}/characters", json={"name": "El sereno", "act": act})
    await client.post(f"{API}/stories/{sid}/characters", json={"name": "La vecina"})

    state = (
        await client.post(f"{API}/stories/{sid}/characters/remove", json={"name": "el sereno"})
    ).json()
    assert "El sereno" not in [c["name"] for c in state["characters"]]
    assert not any("El sereno" in a["on_stage"] for a in state["outline"]["acts"])

    # Un personaje nuevo no repite el id de otro (antes era `len + 1`).
    await client.post(f"{API}/stories/{sid}/characters", json={"name": "El cura"})
    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))
    ids = [p["id"] for p in story.personajes_full]
    assert len(ids) == len(set(ids))

    assert (
        await client.post(f"{API}/stories/{sid}/characters/remove", json={"name": "José"})
    ).status_code == 422  # quien narra
    assert (
        await client.post(f"{API}/stories/{sid}/characters/remove", json={"name": "Nadie"})
    ).status_code == 404


async def test_sumar_lugares_varios(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")

    await client.post(f"{API}/stories/{sid}/scenarios", json={"name": "El galpón"})
    state = (
        await client.post(
            f"{API}/stories/{sid}/scenarios", json={"name": "La ruta  vieja", "act": 3}
        )
    ).json()
    names = [s["name"] for s in state["scenarios"]]
    assert "El galpón" in names and "La ruta vieja" in names
    assert state["outline"]["acts"][2]["scenario"] == "La ruta vieja"
    assert next(s for s in state["scenarios"] if s["name"] == "La ruta vieja")["acts"] == [3]

    # Sin duplicar por mayúsculas; con `act`, queda elegido con su nombre de siempre.
    state = (
        await client.post(f"{API}/stories/{sid}/scenarios", json={"name": "el galpón", "act": 1})
    ).json()
    assert [s["name"] for s in state["scenarios"]].count("El galpón") == 1
    assert state["outline"]["acts"][0]["scenario"] == "El galpón"
    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))
    assert {"El galpón", "La ruta vieja"} <= {s.name for s in story.scenarios}


async def test_borrar_lugar_vacia_los_actos(client):
    sid = (await _create(client))["story_id"]
    state = await _run_job(client, sid, "plan_outline")
    del_plan = state["outline"]["acts"][0]["scenario"]  # un lugar que solo usa la escaleta
    await client.post(f"{API}/stories/{sid}/scenarios", json={"name": "El galpón", "act": 2})
    await client.post(f"{API}/stories/{sid}/scenarios", json={"name": "El galpón", "act": 4})

    state = (
        await client.post(f"{API}/stories/{sid}/scenarios/remove", json={"name": "El galpón"})
    ).json()
    assert "El galpón" not in [s["name"] for s in state["scenarios"]]
    assert (
        state["outline"]["acts"][1]["scenario"] == ""
        and state["outline"]["acts"][3]["scenario"] == ""
    )

    if del_plan:
        state = (
            await client.post(f"{API}/stories/{sid}/scenarios/remove", json={"name": del_plan})
        ).json()
        assert all(a["scenario"] != del_plan for a in state["outline"]["acts"])
    assert (
        await client.post(f"{API}/stories/{sid}/scenarios/remove", json={"name": "Nadie"})
    ).status_code == 404


async def test_un_lugar_sumado_en_los_actos_llega_al_planificador(client):
    """Spec-630 B11: antes, un lugar nuevo vivía solo en el acto y el Planificador no lo veía."""
    from src.application.services.authoring.planner import OutlinePlanner

    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")
    await client.post(f"{API}/stories/{sid}/scenarios", json={"name": "El galpón", "act": 2})
    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))
    assert "ESCENARIOS YA DEFINIDOS: " in (prompt := OutlinePlanner(llm=None)._prompt(story))
    assert "El galpón" in prompt.split("ESCENARIOS YA DEFINIDOS: ")[1].split("\n")[0]
