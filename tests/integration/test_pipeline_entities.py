"""Spec-450 en el pipeline de la escaleta (Spec-530 S7): la amenaza en el prompt de la Voz.

Mismo arnés que el snapshot (job real + LLM que graba), con entidades.
"""

import copy
import uuid

import httpx
import pytest

from src.config import settings
from src.infrastructure.database.connection import init_db
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


def _story(*entities: dict) -> dict:
    story = copy.deepcopy(STORY)
    story["narrator_config"]["entities"] = list(entities)
    return story


@pytest.fixture
def run_pipeline(monkeypatch, tmp_path):
    async def _run(story: dict, regenerate_beat: int | None = None) -> list[str]:
        """Prompts de la Voz (del job completo o, si se pide, solo de la regeneración)."""
        llm = RecordingLLM()
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'p.db'}")
        monkeypatch.setattr(LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: llm))
        await init_db()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/stories?action=save", json=story)
            assert resp.status_code == 201, resp.text
            story_id = resp.json()["id"]
            job = (await client.post(f"/api/v1/stories/{story_id}/jobs", json={})).json()
            await job_manager.wait(uuid.UUID(job["job_id"]))
            done = (await client.get(f"/api/v1/jobs/{job['job_id']}")).json()
            assert done["status"] == "done", done
            if regenerate_beat:
                llm.calls.clear()
                body = {
                    "kind": "regenerate_voz",
                    "beat": regenerate_beat,
                    "narrative_id": done["narrative_id"],
                }
                job = (await client.post(f"/api/v1/stories/{story_id}/jobs", json=body)).json()
                await job_manager.wait(uuid.UUID(job["job_id"]))
                regen = (await client.get(f"/api/v1/jobs/{job['job_id']}")).json()
                assert regen["status"] == "done", regen
        return [c["prompt"] for c in llm.calls if c["role"] == "voz"]

    return _run


def _threat_block(prompt: str) -> str:
    return prompt.split("AMENAZA EN ESTE ACTO")[1].split("\n\n")[0]


async def test_voz_con_senales_no_recibe_nombre_ni_naturaleza(run_pipeline):
    voz = await run_pipeline(_story({**MALA_HORA, "reveal_level": "nunca"}))

    beat1 = _threat_block(voz[0])
    assert "La Mala Hora" not in beat1 and "Ser del folklore" not in beat1
    assert "Una mujer de negro" not in beat1  # la descripción tampoco
    assert "Cómo se percibe: Olor a azufre y un silbido" in beat1
    assert "La Mala Hora" not in _threat_block(voz[2])


async def test_voz_explicita_nombra_la_entidad(run_pipeline):
    voz = await run_pipeline(_story({**MALA_HORA, "reveal_level": "explicita"}))

    assert "- La Mala Hora — Ser del folklore" in _threat_block(voz[0])


async def test_sin_entidades_la_voz_no_menciona_la_amenaza(run_pipeline):
    for prompt in await run_pipeline(_story()):
        assert "AMENAZA EN ESTE ACTO" not in prompt


async def test_regenerar_un_acto_mantiene_la_amenaza(run_pipeline):
    (voz,) = await run_pipeline(_story(MALA_HORA), regenerate_beat=2)

    assert "AMENAZA EN ESTE ACTO" in voz
    assert "Cómo se percibe" in _threat_block(voz)
