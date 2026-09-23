"""Spec-440 T2.2/T2.3: catálogo de géneros y validación del par en el API."""

from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.infrastructure.database.connection import init_db
from src.main import app

_BASE = {
    "title": "t",
    "protagonista": "Rosa",
    "relator": "Primera persona",
    "escenarios": "",
    "sinopsis": "Algo pasa.",
}


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'c.db'}")
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _post(client, genero: str, subgenero: str) -> httpx.Response:
    body = {**_BASE, "genero": genero, "subgenero": subgenero}
    return await client.post("/api/v1/stories?action=save", json=body)


async def test_catalogo_ordenado_con_subgeneros(client):
    resp = await client.get("/api/v1/catalog/genres")

    assert resp.status_code == 200
    genres = resp.json()
    assert [g["id"] for g in genres][:2] == ["terror_psicologico", "horror_cosmico"]
    assert len(genres) == 8
    body = next(g for g in genres if g["id"] == "body_horror")
    assert body["label"] == "Horror Corporal"
    assert [s["id"] for s in body["subgenres"]] == [
        "mutacion",
        "contagio",
        "quirurgico",
        "parasitario",
        "decadencia",
        "otro",
    ]
    assert body["subgenres"][-1] == {"id": "otro", "label": "Otro estilo"}


@pytest.mark.parametrize(
    ("genero", "subgenero"),
    [("folk_horror", "rural"), ("body_horror", "otro"), ("suspenso", ""), ("", "")],
)
async def test_post_con_par_valido(client, genero, subgenero):
    resp = await _post(client, genero, subgenero)

    assert resp.status_code == 201, resp.text
    story = (await client.get(f"/api/v1/stories/{resp.json()['id']}")).json()
    assert (story["genero"], story["subgenero"]) == (genero, subgenero)


@pytest.mark.parametrize(
    ("genero", "subgenero", "detail"),
    [
        ("body_horror", "rural", "El subgénero 'rural' no corresponde al género 'body_horror'"),
        ("inventado", "", "El género 'inventado' no existe en el catálogo"),
        ("inventado", "rural", "El género 'inventado' no existe en el catálogo"),
    ],
)
async def test_post_con_par_invalido_422(client, genero, subgenero, detail):
    resp = await _post(client, genero, subgenero)

    assert resp.status_code == 422
    assert resp.json()["detail"] == detail


async def test_patch_con_par_invalido_422_y_no_cambia_nada(client):
    story_id = (await _post(client, "folk_horror", "rural")).json()["id"]

    body = {**_BASE, "title": "otro", "genero": "body_horror", "subgenero": "rural"}
    resp = await client.patch(f"/api/v1/stories/{story_id}", json=body)

    assert resp.status_code == 422
    story = (await client.get(f"/api/v1/stories/{story_id}")).json()
    assert (story["title"], story["genero"], story["subgenero"]) == ("t", "folk_horror", "rural")


async def test_integrity_error_residual_es_422(client, monkeypatch):
    """Si la validación no lo atrapa, la FK de `story` rechaza y el API responde 422."""
    from src.infrastructure.database.repositories import SQLGenreRepository

    async def always(*_a, **_k):
        return True

    monkeypatch.setattr(SQLGenreRepository, "exists", always)

    resp = await _post(client, "body_horror", "rural")

    assert resp.status_code == 422
    assert "género/subgénero" in resp.json()["detail"]


async def test_catalogo_trae_naturalezas_por_genero(client):
    """Spec-450 T0.2."""
    genres = {g["id"]: g for g in (await client.get("/api/v1/catalog/genres")).json()}

    assert genres["suspenso"]["entity_natures"] == [
        {"id": "humano", "label": "Humano (asesino, acosador)"},
        {"id": "culto", "label": "Culto / colectivo"},
        {"id": "desconocida", "label": "Desconocida / ambigua"},
    ]
    for g in genres.values():
        assert g["entity_natures"][-1]["id"] == "desconocida"


@pytest.mark.usefixtures("client")  # DB temporal con init_db()
async def test_repo_naturalezas_de_un_genero():
    from src.infrastructure.database.repositories import SQLGenreRepository

    repo = SQLGenreRepository()
    ids = [n.id for n in await repo.natures_of("folk_horror")]

    # Orden del catálogo (order_index), no el del mapeo.
    assert ids == ["espiritu", "demonio", "culto", "lugar", "folklorica", "desconocida"]
    assert await repo.natures_of("inventado") == []
    assert await repo.nature_allowed("folk_horror", "folklorica")
    assert not await repo.nature_allowed("suspenso", "demonio")
