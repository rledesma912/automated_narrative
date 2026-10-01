"""Spec-610 T1.2: PUT /generated-narratives/{id}/acts/{n} (corregir el relato en la web)."""

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.domain.jobs import Job, JobKind
from src.domain.models import GeneratedNarrative
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import (
    SQLGeneratedNarrativeRepository,
    SQLJobRepository,
)
from src.main import app

_PAYLOAD = {
    "title": "No te detengas en el bosque",
    "protagonista": "Ernesto: camionero",
    "relator": "Primera persona en pasado. Narrador: Ernesto.",
    "escenarios": "El bosque: la ruta",
    "sinopsis": "Un camión se queda en el bosque.",
}
_CONTENT = (
    "## Acto 1\n\nNunca se lo conté a nadie.\n\nEsa noche venía manejando.\n\n"
    "## Acto 2\n\nBajé a mirar el motor y había un silencio sepulcral."
)


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'acts.db'}")
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _narrative(client: httpx.AsyncClient) -> GeneratedNarrative:
    resp = await client.post("/api/v1/stories?action=save", json=_PAYLOAD)
    assert resp.status_code in (200, 201), resp.text
    narrative = GeneratedNarrative(
        story_template_id=uuid.UUID(resp.json()["id"]), title="v1", content=_CONTENT
    )
    return await SQLGeneratedNarrativeRepository().save(narrative)


def _url(narrative_id, number) -> str:
    return f"/api/v1/generated-narratives/{narrative_id}/acts/{number}"


async def test_corrige_un_acto_y_no_toca_los_demas(client):
    narrative = await _narrative(client)

    resp = await client.put(
        _url(narrative.id, 2), json={"text": "Bajé a mirar el motor.\r\n\r\n\r\nNo vi nada.  "}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "number": 2,
        "text": "Bajé a mirar el motor.\n\nNo vi nada.",
        "paragraphs": 2,
        "words": 8,
    }
    saved = await SQLGeneratedNarrativeRepository().get_by_id(narrative.id)
    assert saved.content == (
        "## Acto 1\n\nNunca se lo conté a nadie.\n\nEsa noche venía manejando.\n\n"
        "## Acto 2\n\nBajé a mirar el motor.\n\nNo vi nada."
    )
    assert (saved.title, saved.created_at) == (narrative.title, narrative.created_at)


async def test_el_control_de_repeticion_mira_lo_corregido(client):
    narrative = await _narrative(client)
    antes = await client.get(f"/api/v1/generated-narratives/{narrative.id}/repetition")
    assert antes.json()["acts"][1]["cliches"]

    await client.put(_url(narrative.id, 2), json={"text": "Bajé a mirar el motor."})

    despues = await client.get(f"/api/v1/generated-narratives/{narrative.id}/repetition")
    assert despues.json()["acts"][1]["cliches"] == []


async def test_acto_vacio(client):
    narrative = await _narrative(client)
    resp = await client.put(_url(narrative.id, 1), json={"text": " \n\n  "})
    assert resp.status_code == 422
    assert "vacío" in resp.json()["detail"]


async def test_acto_que_no_existe(client):
    narrative = await _narrative(client)
    resp = await client.put(_url(narrative.id, 4), json={"text": "Algo."})
    assert resp.status_code == 404
    assert "acto 4" in resp.json()["detail"]


async def test_relato_que_no_existe(client):
    resp = await client.put(_url(uuid.uuid4(), 1), json={"text": "Algo."})
    assert resp.status_code == 404


async def test_id_invalido(client):
    resp = await client.put(_url("no-es-uuid", 1), json={"text": "Algo."})
    assert resp.status_code == 400


async def test_con_la_ia_trabajando_en_la_historia(client):
    narrative = await _narrative(client)
    job = await SQLJobRepository().create(
        Job(story_id=narrative.story_template_id, kind=JobKind.REGENERATE_VOZ)
    )

    resp = await client.put(_url(narrative.id, 1), json={"text": "Algo."})

    assert resp.status_code == 409
    assert resp.headers["x-job-id"] == str(job.id)
    saved = await SQLGeneratedNarrativeRepository().get_by_id(narrative.id)
    assert saved.content == _CONTENT


async def test_la_web_lee_el_ritmo_de_lectura(client):
    resp = await client.get("/api/v1/video/lectura")
    assert resp.status_code == 200
    assert resp.json() == {
        "palabras_por_minuto": 150,
        "episodio_minutos": {"desde": 12, "hasta": 17},
    }
