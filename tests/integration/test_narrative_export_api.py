"""Spec-490 T1.2: GET /generated-narratives/{id}/export.md."""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

import httpx
import pytest

from src.config import settings
from src.domain.models import GeneratedNarrative
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLGeneratedNarrativeRepository
from src.main import app
from src.utils import ARGENTINA_TZ

_PAYLOAD = {
    "title": "El monte prohibido",
    "protagonista": "María: narradora [observadora]",
    "relator": "Primera persona en pasado. Narradora: María.",
    "escenarios": "El monte: cerrado",
    "sinopsis": "Algo pasa en el monte.",
}


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'export.db'}")
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _narrative(client: httpx.AsyncClient) -> GeneratedNarrative:
    resp = await client.post("/api/v1/stories?action=save", json=_PAYLOAD)
    assert resp.status_code in (200, 201), resp.text
    narrative = GeneratedNarrative(
        story_template_id=uuid.UUID(resp.json()["id"]),
        title="El monte prohibido · 2026-09-24 15:30",
        content="## Acto 1\n\n- ¿Quién anda ahí?\n\n## Acto 2\n\n*Nadie* respondió.",
        created_at=datetime(2026, 9, 24, 15, 30, tzinfo=ARGENTINA_TZ),
    )
    return await SQLGeneratedNarrativeRepository().save(narrative)


async def test_descarga_el_md(client):
    narrative = await _narrative(client)

    resp = await client.get(f"/api/v1/generated-narratives/{narrative.id}/export.md")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
    assert resp.headers["content-disposition"] == (
        'attachment; filename="el-monte-prohibido-2026-09-24-1530.md"'
    )
    assert resp.text == (
        "# El monte prohibido\n\n"
        "## Acto 1\n\n—¿Quién anda ahí?\n\n"
        "[pause=1500]\n\n"
        "## Acto 2\n\nNadie respondió.\n"
    )


async def test_id_invalido(client):
    resp = await client.get("/api/v1/generated-narratives/no-es-uuid/export.md")
    assert resp.status_code == 400


async def test_variante_inexistente(client):
    resp = await client.get(f"/api/v1/generated-narratives/{uuid.uuid4()}/export.md")
    assert resp.status_code == 404
