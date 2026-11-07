"""Spec-750 S3: cada versión del relato guarda su largo.

La media y la larga tienen 5 actos: el largo de una versión ya no se deduce de cuántos
actos tiene. Las versiones viejas (sin el dato) sí: 3 = corto, 5 = media.
"""

import sqlite3

from src.application.services import narrative_acts
from src.application.services.video.config import video_config
from src.application.services.video.prompts import VideoScriptPrompts
from src.application.services.video.service import VideoScriptService
from src.config import settings
from src.domain.models import GeneratedNarrative, Story
from src.infrastructure.adapters import MockLLMAdapter
from tests.integration.test_authoring_api import API
from tests.integration.test_relato_corto import _create, _generate, client  # noqa: F401
from tests.unit.application.video.test_video_corto import _contenido


def _db() -> str:
    return settings.database_url.removeprefix("sqlite+aiosqlite:///")


async def _version(client, nid: str) -> dict:  # noqa: F811
    return (await client.get(f"/api/v1/generated-narratives/{nid}")).json()


async def test_la_version_guarda_el_largo_de_la_historia(client):  # noqa: F811
    media = (await _create(client))["story_id"]
    larga = (await _create(client, structure="largo"))["story_id"]
    nid_media = (await _generate(client, media))["narrative_id"]
    nid_larga = (await _generate(client, larga))["narrative_id"]

    assert (await _version(client, nid_media))["structure"] == "medio"
    assert (await _version(client, nid_larga))["structure"] == "largo"
    lista = (await client.get(f"/api/v1/story-templates/{larga}/narratives")).json()
    assert [v["structure"] for v in lista] == ["largo"]
    con = sqlite3.connect(_db())
    guardado = dict(con.execute("SELECT id, structure FROM generated_narrative"))
    assert guardado == {nid_media: "medio", nid_larga: "largo"}


async def test_una_version_vieja_se_deduce_por_sus_actos(client):  # noqa: F811
    media = (await _create(client))["story_id"]
    corto = (await _create(client, structure="corto"))["story_id"]
    nid_media = (await _generate(client, media))["narrative_id"]
    nid_corto = (await _generate(client, corto))["narrative_id"]
    con = sqlite3.connect(_db())
    con.execute("UPDATE generated_narrative SET structure = NULL")
    con.commit()

    assert (await _version(client, nid_media))["structure"] == "medio"
    assert (await _version(client, nid_corto))["structure"] == "corto"


async def test_una_version_media_no_se_regenera_si_la_historia_paso_a_larga(client):  # noqa: F811
    """D11 con los mismos 5 actos: la escaleta de la larga no se corresponde con su prosa."""
    sid = (await _create(client))["story_id"]
    job = await _generate(client, sid)
    resp = await client.put(f"{API}/stories/{sid}/structure", json={"structure": "largo"})
    assert resp.status_code == 200, resp.text
    await _generate(client, sid)

    resp = await client.post(
        f"/api/v1/stories/{sid}/jobs",
        json={"kind": "regenerate_voz", "beat": 2, "narrative_id": job["narrative_id"]},
    )

    assert resp.status_code == 422
    assert "otro largo" in resp.json()["detail"]


async def test_el_episodio_de_la_larga(client):  # noqa: F811
    larga = (await client.get("/api/v1/video/lectura?estructura=largo&actos=5")).json()
    assert larga["episodio_minutos"] == {"desde": 30, "hasta": 38}
    assert larga["estructura"] == "largo"
    media = (await client.get("/api/v1/video/lectura?actos=5")).json()
    assert media["episodio_minutos"] == {"desde": 12, "hasta": 17}


def test_el_video_de_la_larga_pide_sus_momentos():
    story = Story(title="t", protagonista="Ana", relator="Primera persona", sinopsis="s")
    acts = narrative_acts.split(_contenido(5, 6))
    acts.structure = "largo"
    _, user = VideoScriptPrompts(video_config()).build(story, acts)
    assert "entre 20 y 28 momentos" in user


async def test_con_el_mock_sale_un_paquete_largo_valido():
    story = Story(title="t", protagonista="Ana", relator="Primera persona", sinopsis="s")
    narrative = GeneratedNarrative(
        story_template_id=story.id, title="v", content=_contenido(5, 8), structure="largo"
    )
    script = await VideoScriptService(MockLLMAdapter()).generate(story, narrative)
    assert 20 <= len(script.momentos) <= 28
