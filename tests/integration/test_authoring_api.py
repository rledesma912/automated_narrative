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
    # Spec-680 C1: la de siempre primero, sin los patrones (son del control).
    assert [h["id"] for h in data["hablas"]] == ["rioplatense", "mexicano", "neutro", "espana"]
    assert set(data["hablas"][0]) == {"id", "label", "detail"}


async def test_habla_se_guarda_y_vuelve(client):
    """Spec-680 C1: el autoguardado de «Tu idea» lleva el habla; una que no existe, 422."""
    state = await _create(client)
    story_id = state["story_id"]
    put = await client.put(f"{API}/stories/{story_id}/direction", json=FORM | {"habla": "mexicano"})
    assert put.status_code == 200, put.text
    again = (await client.get(f"{API}/stories/{story_id}")).json()
    assert again["direction"]["habla"] == "mexicano"
    bad = await client.put(f"{API}/stories/{story_id}/direction", json=FORM | {"habla": "klingon"})
    assert bad.status_code == 422


async def test_crear_desde_la_direccion(client):
    state = await _create(client)

    assert state["direction"] == FORM | {
        "narrator": "José",
        "effect_other": "",
        "threat": None,
        # Spec-670: sin forma ni giro = la forma de siempre.
        "form": "",
        "ingredient": "",
        "form_other": "",
        "form_suggested": "",
        "form_reason": "",
        "habla": "",  # Spec-680 C1: la de siempre
    }
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
    assert journal.narrator_traits == ["silba cuando está nervioso"]
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
        "comparisons": [],
        "comparison_count": 0,
        "too_literary": False,
        "gestures": [],
        "foreign": [],
        "foreign_count": 0,
        "triads": [],
        "triad_count": 0,
        "too_listy": False,
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


# ── Spec-670: el molde en la dirección ─────────────────────────────────────


async def test_el_autoguardado_conserva_lo_que_sugirio_la_ia(client):
    """D13: `form_suggested` y `form_reason` no vienen del formulario; un guardado de
    «Tu idea» no los borra (la trampa de la D9 de la Spec-650)."""
    from src.infrastructure.database.repositories import SQLStoryRepository

    sid = (await _create(client))["story_id"]
    repo = SQLStoryRepository()
    story = await repo.get_by_id(sid)
    await repo.update_direction(
        sid,
        story.direction.model_copy(
            update={
                "form": "asedio",
                "form_suggested": "asedio",
                "form_reason": "Nadie la provoca.",
            }
        ),
    )
    resp = await client.put(f"{API}/stories/{sid}/direction", json={**FORM, "form": "regla"})
    assert resp.status_code == 200, resp.text
    d = resp.json()["direction"]
    assert (d["form"], d["form_suggested"], d["form_reason"]) == (
        "regla",
        "asedio",
        "Nadie la provoca.",
    )


@pytest.mark.parametrize("campo", ["form", "ingredient"])
async def test_forma_o_giro_desconocido_422(client, campo):
    sid = (await _create(client))["story_id"]
    resp = await client.put(f"{API}/stories/{sid}/direction", json={**FORM, campo: "no-existe"})
    assert resp.status_code == 422
    assert "no-existe" in resp.json()["detail"]


async def test_yaml_ida_y_vuelta_conserva_la_forma_y_el_giro(client):
    """Spec-670 D3: `export-yaml` / `import-yaml` llevan la forma y el giro (dentro de la
    dirección); un YAML sin forma es la de siempre."""
    import uuid

    import yaml

    from src.application.services.authoring import molde
    from src.application.use_cases.create_story import CreateStoryUseCase
    from src.infrastructure.database.repositories import SQLGenreRepository, SQLStoryRepository
    from src.infrastructure.exporters import YamlStoryExporter
    from src.infrastructure.loaders import YamlStoryLoader

    sid = (await _create(client, form="asedio", ingredient="regla_rara"))["story_id"]
    story = await SQLStoryRepository().get_by_id(uuid.UUID(sid))
    text = YamlStoryExporter().export(story)
    data = yaml.safe_load(text)
    assert (data["direction"]["form"], data["direction"]["ingredient"]) == ("asedio", "regla_rara")

    repo, genres = SQLStoryRepository(), SQLGenreRepository()
    again = await CreateStoryUseCase(repo, genres).execute(YamlStoryLoader().load(text))
    assert (again.direction.form, again.direction.ingredient) == ("asedio", "regla_rara")

    for key in ("form", "ingredient", "form_other", "form_suggested", "form_reason"):
        data["direction"].pop(key)
    viejo = await CreateStoryUseCase(repo, genres).execute(YamlStoryLoader().load_from_dict(data))
    assert molde.for_story(viejo).forma.id == "regla"


async def test_la_ia_sugiere_la_forma_y_se_guarda(client):
    """Spec-670 D1: el job `suggest_form` guarda la sugerencia y su motivo; si la persona
    no había elegido una forma, también la deja elegida."""
    sid = (await _create(client))["story_id"]
    d = (await _run_job(client, sid, "suggest_form"))["direction"]
    assert (d["form"], d["form_suggested"]) == ("asedio", "asedio")  # el mock elige la segunda
    assert d["form_reason"] == "Por cómo es tu idea."


async def test_la_sugerencia_no_pisa_la_forma_que_eligio_la_persona(client):
    sid = (await _create(client, form="lugar"))["story_id"]
    await _run_job(client, sid, "suggest_form")
    d = (await client.get(f"{API}/stories/{sid}")).json()["direction"]
    assert (d["form"], d["form_suggested"]) == ("lugar", "asedio")


async def test_control_de_gestos_y_de_otra_habla(client):
    """Spec-680 C3: el mate que no trae el autor y el voseo en una historia mexicana."""
    from src.domain.models import GeneratedNarrative
    from src.infrastructure.database.repositories import SQLGeneratedNarrativeRepository

    sid = (await _create(client, habla="mexicano"))["story_id"]
    narrative = GeneratedNarrative(
        story_template_id=uuid.UUID(sid),
        title="R",
        content="## Acto 1\n\nTodos saben a qué hora abrís la tienda. Me cebé un mate y salí.",
    )
    await SQLGeneratedNarrativeRepository().save(narrative)

    act = (await client.get(f"/api/v1/generated-narratives/{narrative.id}/repetition")).json()[
        "acts"
    ][0]
    assert act["gestures"] == [{"gesto": "tomar mate, cebar mate, el termo", "texto": "un mate"}]
    assert (act["foreign"], act["foreign_count"]) == (["abrís"], 1)


# ── Spec-690: el final sale de la idea ──────────────────────────────────────

IDEA_CON_FINAL = "José ve por el espejo a una mujer que murió en su micro. Al final la deja bajar."


async def _final_item(client, sid: str) -> dict:
    state = (await client.get(f"{API}/stories/{sid}")).json()
    return next(w for w in state["workshop"]["items"] if w["criterion"] == "final")


@pytest.mark.parametrize("kind", ["consult", "plan_outline"])
async def test_el_final_sale_de_la_idea(client, kind):
    sid = (await _create(client, premise=IDEA_CON_FINAL, ending=""))["story_id"]
    await _run_job(client, sid, kind)
    final = await _final_item(client, sid)
    assert (final["status"], final["answer"]) == ("intencional", "Al final la deja bajar.")


async def test_con_el_final_viejo_no_se_saca_de_la_idea(client):
    sid = (await _create(client, premise=IDEA_CON_FINAL))[
        "story_id"
    ]  # FORM trae «Descansa en paz.»
    await _run_job(client, sid, "consult")
    assert (await _final_item(client, sid))["answer"] == "Descansa en paz."


async def test_cambiar_el_final_sacado_de_la_idea_lo_deja_decidido(client):
    """D17: «Cambiar» en «Cómo termina» no lo vuelve una respuesta común."""
    sid = (await _create(client, premise=IDEA_CON_FINAL, ending=""))["story_id"]
    await _run_job(client, sid, "consult")
    resp = await client.patch(
        f"{API}/stories/{sid}/workshop/final",
        json={"action": "answer", "text": "La deja bajar y llora."},
    )
    assert resp.status_code == 200
    final = await _final_item(client, sid)
    assert (final["status"], final["answer"]) == ("intencional", "La deja bajar y llora.")


async def test_tu_idea_sin_el_campo_no_borra_el_final_viejo(client):
    """S3: el autoguardado de «Tu idea» ya no trae `ending`; el de una historia vieja queda."""
    sid = (await _create(client))["story_id"]  # FORM trae «Descansa en paz.»
    sin_final = {k: v for k, v in FORM.items() if k not in ("ending", "ending_intentional")}
    resp = await client.put(f"{API}/stories/{sid}/direction", json={**sin_final, "title": "Otra"})
    assert resp.status_code == 200
    assert resp.json()["direction"]["ending"] == "Descansa en paz."


async def test_preguntas_marca_el_final_de_la_idea(client):
    sid = (await _create(client, premise=IDEA_CON_FINAL, ending=""))["story_id"]
    await _run_job(client, sid, "consult")
    final = await _final_item(client, sid)
    assert final["de_la_idea"] is True
    otros = (await client.get(f"{API}/stories/{sid}")).json()["workshop"]["items"]
    assert not any(w["de_la_idea"] for w in otros if w["criterion"] != "final")


# ── Spec-700 B: los personajes de la autora ─────────────────────────────────


async def _con_quienes_estan(client, sid: str, por_acto: dict[int, list[str]]) -> None:
    for n, names in por_acto.items():
        resp = await client.put(
            f"{API}/stories/{sid}/outline/{n}", json={"events": ["Pasa algo"], "on_stage": names}
        )
        assert resp.status_code == 200, resp.text


def _elenco(state, n: int) -> dict[str, dict]:
    return {
        w["key"]: w
        for w in state["outline"]["acts"][n - 1]["warnings"]
        if w["key"].startswith("elenco:")
    }


async def test_los_personajes_de_la_idea_se_suman_solos(client):
    premise = "José maneja de noche; Marta, la de la boletería, le avisa de la mujer del espejo."
    sid = (await _create(client, premise=premise))["story_id"]
    await _run_job(client, sid, "plan_outline")
    await _con_quienes_estan(client, sid, {2: ["José", "Marta", "El sereno"], 3: ["El sereno"]})

    state = await _run_job(client, sid, "verify_outline")

    assert [c["name"] for c in state["characters"]] == ["José", "Marta"]
    assert set(_elenco(state, 2)) == {"elenco:el sereno"}  # Marta no se pregunta
    sereno = _elenco(state, 3)["elenco:el sereno"]
    assert sereno["subject"] == "El sereno" and sereno["similar"] == ""
    assert sereno["text"].startswith("La IA puso a «El sereno»")


async def test_sumar_un_personaje_resuelve_su_aviso_en_todos_los_actos(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")
    await _con_quienes_estan(client, sid, {2: ["José", "El sereno"], 4: ["El sereno"]})
    state = await _run_job(client, sid, "verify_outline")
    assert "elenco:el sereno" in _elenco(state, 4)

    state = (
        await client.post(f"{API}/stories/{sid}/characters", json={"name": "El sereno", "act": 2})
    ).json()

    assert not _elenco(state, 2) and not _elenco(state, 4)


async def test_es_uno_de_la_lista_escrito_distinto(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")
    await client.post(f"{API}/stories/{sid}/characters", json={"name": "Amigas de José"})
    await _con_quienes_estan(
        client, sid, {2: ["José", "Amigos de José"], 3: ["Amigos de José", "Amigas de José"]}
    )
    state = await _run_job(client, sid, "verify_outline")
    assert _elenco(state, 2)["elenco:amigos de jose"]["similar"] == "Amigas de José"

    state = (
        await client.post(
            f"{API}/stories/{sid}/characters/same",
            json={"name": "amigos de josé", "same_as": "Amigas de José"},
        )
    ).json()

    acts = state["outline"]["acts"]
    assert acts[1]["on_stage"] == ["José", "Amigas de José"]
    assert acts[2]["on_stage"] == ["Amigas de José"]  # sin repetir
    assert not _elenco(state, 2) and not _elenco(state, 3)
    assert [c["name"] for c in state["characters"]] == ["José", "Amigas de José"]
    resp = await client.post(
        f"{API}/stories/{sid}/characters/same", json={"name": "X", "same_as": "Nadie"}
    )
    assert resp.status_code == 404


async def test_sacar_el_nombre_del_acto_o_borrarlo_resuelve_el_aviso(client):
    sid = (await _create(client))["story_id"]
    await _run_job(client, sid, "plan_outline")
    await _con_quienes_estan(client, sid, {2: ["José", "El sereno", "El cura"], 3: ["El cura"]})
    await _run_job(client, sid, "verify_outline")

    state = (
        await client.put(
            f"{API}/stories/{sid}/outline/2", json={"events": ["Pasa algo"], "on_stage": ["José"]}
        )
    ).json()
    assert not _elenco(state, 2)
    assert "elenco:el cura" in _elenco(state, 3)  # el otro acto no cambia

    await client.post(f"{API}/stories/{sid}/characters", json={"name": "El cura"})
    state = (
        await client.post(f"{API}/stories/{sid}/characters/remove", json={"name": "El cura"})
    ).json()
    assert not _elenco(state, 3) and state["outline"]["acts"][2]["on_stage"] == []
