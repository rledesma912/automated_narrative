"""Spec-450 T3.2–T3.4: las entidades en los prompts de cada rol del pipeline.

Mismo arnés que el snapshot de T3.1 (job real + LLM que graba), con entidades.
"""

import copy
import uuid

import httpx
import pytest

from src.config import settings
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.main import app
from src.presentation.runtime import job_manager
from tests.integration.test_pipeline_prompts_snapshot import STORY
from tests.support.recording_llm import RecordingLLM

MALA_HORA = {
    "name": "La Mala Hora",
    "nature": "folklorica",
    "description": "Una mujer de negro que aparece a la siesta",
    "manifestations": "Olor a azufre y un silbido",
    "limits": "No cruza el agua corriente",
}
CULTO = {"name": "Los del monte", "nature": "culto", "reveal_level": "explicita"}
ENTITY_STATE = "La Mala Hora rondó el galpón; Rosa oyó el silbido."


def _story(*entities: dict) -> dict:
    story = copy.deepcopy(STORY)
    story["narrator_config"]["entities"] = list(entities)
    return story


class Run:
    def __init__(self, llm: RecordingLLM):
        self.llm = llm
        self.story_id = ""
        self.narrative_id = ""

    def prompts(self, role: str) -> list[str]:
        return [c["prompt"] for c in self.llm.calls if c["role"] == role]


@pytest.fixture
def run_pipeline(monkeypatch, tmp_path):
    async def _run(story: dict, regenerate_beat: int | None = None) -> Run:
        llm = RecordingLLM(journal_extra={"entity_state": ENTITY_STATE})
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'p.db'}")
        monkeypatch.setattr(LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: llm))
        await init_db()
        run = Run(llm)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/stories?action=save", json=story)
            assert resp.status_code == 201, resp.text
            run.story_id = resp.json()["id"]
            job = (await client.post(f"/api/v1/stories/{run.story_id}/jobs", json={})).json()
            await job_manager.wait(uuid.UUID(job["job_id"]))
            done = (await client.get(f"/api/v1/jobs/{job['job_id']}")).json()
            assert done["status"] == "done", done
            run.narrative_id = done["narrative_id"]
            if regenerate_beat:
                llm.calls.clear()
                body = {
                    "kind": "regenerate_voz",
                    "beat": regenerate_beat,
                    "narrative_id": run.narrative_id,
                }
                job = (await client.post(f"/api/v1/stories/{run.story_id}/jobs", json=body)).json()
                await job_manager.wait(uuid.UUID(job["job_id"]))
        return run

    return _run


async def test_analyst_recibe_las_fichas_con_la_principal_primero(run_pipeline):
    run = await run_pipeline(_story(MALA_HORA, CULTO))

    (analyst,) = run.prompts("story_analyst")
    block = analyst.split("AMENAZA (la primera es la principal")[1]
    assert block.index("La Mala Hora — Ser del folklore [principal]") < block.index(
        "Los del monte — Culto / colectivo"
    )
    assert "Límites: No cruza el agua corriente" in block


async def test_mapper_recibe_la_exposicion_de_cada_entidad_por_acto(run_pipeline):
    run = await run_pipeline(_story(MALA_HORA, CULTO))

    mappers = run.prompts("director")
    assert "### AMENAZA EN ESTE ACTO" in mappers[0]
    # Beat 1: la principal (insinuada) solo señales; el culto (explícita) presencia abierta.
    assert "En este acto: Solo señales" in mappers[0]
    assert "En este acto: Presencia abierta" in mappers[0]
    assert "En este acto: Revelación" in mappers[2]


async def test_voz_con_senales_no_recibe_nombre_ni_naturaleza(run_pipeline):
    run = await run_pipeline(_story({**MALA_HORA, "reveal_level": "nunca"}))

    voz = run.prompts("voz")
    beat1 = voz[0].split("AMENAZA EN ESTE ACTO")[1].split("\n\n")[0]
    assert "La Mala Hora" not in beat1 and "Ser del folklore" not in beat1
    assert "Una mujer de negro" not in beat1  # la descripción tampoco
    assert "Cómo se percibe: Olor a azufre y un silbido" in beat1
    # nunca: el beat 3 no pide presencia directa sino señales intensas.
    assert "PROHIBIDO: explicar origen o reglas completas del fenomeno" in voz[2]
    assert "La Mala Hora" not in voz[2].split("AMENAZA EN ESTE ACTO")[1].split("\n\n")[0]


async def test_voz_explicita_nombra_la_entidad_y_levanta_los_must_not(run_pipeline):
    run = await run_pipeline(_story({**MALA_HORA, "reveal_level": "explicita"}))

    beat1 = run.prompts("voz")[0]
    assert "- La Mala Hora — Ser del folklore" in beat1
    assert "confirmar lo paranormal" not in beat1


async def test_sin_entidades_ningun_rol_menciona_la_amenaza(run_pipeline):
    run = await run_pipeline(_story())

    for call in run.llm.calls:
        assert "AMENAZA" not in call["prompt"].upper().replace("AMENAZA O PRESENCIA", "")
        assert "entity_state" not in call["prompt"]


async def test_journal_devuelve_el_estado_y_llega_a_la_voz_siguiente(run_pipeline):
    run = await run_pipeline(_story(MALA_HORA))

    journals = run.prompts("journal")
    assert '"entity_state"' in journals[0]
    assert f"- Amenaza: {ENTITY_STATE}" in journals[1]
    voz = run.prompts("voz")
    assert "Amenaza hasta ahora" not in voz[0]
    assert f"Amenaza hasta ahora: {ENTITY_STATE}" in voz[1]

    repo = SQLStoryRepository()
    assert (await repo.get_journal(uuid.UUID(run.story_id), 3)).entity_state == ENTITY_STATE


async def test_regenerar_un_acto_recibe_el_estado_de_la_entidad(run_pipeline):
    run = await run_pipeline(_story(MALA_HORA), regenerate_beat=2)

    (voz,) = run.prompts("voz")
    assert f"Amenaza hasta ahora: {ENTITY_STATE}" in voz
    assert "AMENAZA EN ESTE ACTO" in voz
