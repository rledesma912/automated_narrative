"""Spec-795 §3: el tablero por la API, con las entregas en una carpeta temporal."""

from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.infrastructure.database.connection import init_db
from src.main import app
from tests.support.tablero import entrega

ID = "2026-11-26-calabaza-hoja"


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[tuple[httpx.AsyncClient, object]]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    monkeypatch.setattr(settings, "tablero_dir", str(tmp_path / "tablero"))
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, tmp_path / "tablero"


async def test_tablero_vacio(client):
    c, _ = client
    assert (await c.get("/api/v1/tablero/entregas")).json() == {"proyectos": [], "entregas": []}


async def test_listar_filtrar_y_saltear_invalidas(client):
    c, base = client
    entrega(base, ID)
    entrega(base, "2026-11-20-miniaturas-peter", proyecto="miniaturas")
    entrega(base, "2026-11-21-otra", proyecto="algo-nuevo")
    rota = entrega(base, "2026-11-25-rota")
    (rota / "b.png").unlink()
    datos = (await c.get("/api/v1/tablero/entregas")).json()
    assert [e["id"] for e in datos["entregas"]] == [
        ID,
        "2026-11-21-otra",
        "2026-11-20-miniaturas-peter",
    ]
    assert datos["proyectos"] == [
        {"slug": "calabaza", "nombre": "La calabaza de la cripta"},
        {"slug": "miniaturas", "nombre": "Miniaturas"},
        {"slug": "algo-nuevo", "nombre": "algo-nuevo"},  # sin nombre en config: el slug
    ]
    primera = datos["entregas"][0]
    assert primera["total_archivos"] == 3 and primera["opiniones"] == 0
    assert primera["archivos"][0]["url"] == f"/api/v1/tablero/entregas/{ID}/archivos/a.png"
    solo = (await c.get("/api/v1/tablero/entregas?proyecto=miniaturas")).json()["entregas"]
    assert [e["id"] for e in solo] == ["2026-11-20-miniaturas-peter"]
    malas = (await c.get("/api/v1/tablero/invalidas")).json()
    assert malas[0]["id"] == "2026-11-25-rota" and "b.png" in malas[0]["motivo"]


async def test_ver_y_servir_archivos(client):
    c, base = client
    carpeta = entrega(base, ID)
    (carpeta / "no_declarado.png").write_bytes(b"x")
    e = (await c.get(f"/api/v1/tablero/entregas/{ID}")).json()
    assert e["proyecto_nombre"] == "La calabaza de la cripta"
    assert e["filas"][0]["titulo"] == "Maestra"
    assert [a["leyenda"] for a in e["filas"][0]["archivos"]] == ["A", "B"]
    assert e["sueltas"][0]["tipo_medio"] == "imagen" and e["sueltas"][0]["me_gusta"] == 0
    r = await c.get(f"/api/v1/tablero/entregas/{ID}/archivos/a.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    svg = await c.get(f"/api/v1/tablero/entregas/{ID}/archivos/vistas.svg")
    assert svg.headers["content-security-policy"] == "script-src 'none'"
    for nombre in ("no_declarado.png", "entrega.yaml", "..%2Ft.db"):
        assert (await c.get(f"/api/v1/tablero/entregas/{ID}/archivos/{nombre}")).status_code == 404
    assert (await c.get("/api/v1/tablero/entregas/2026-01-01-no-esta")).status_code == 404


async def test_opinar_contar_y_sacar(client):
    c, base = client
    entrega(base, ID)
    url = f"/api/v1/tablero/entregas/{ID}/opiniones"
    for tipo in ("me_gusta", "me_gusta", "no_va"):
        assert (await c.post(url, json={"archivo": "a.png", "tipo": tipo})).status_code == 201
    nota = (
        await c.post(url, json={"archivo": "a.png", "tipo": "nota", "texto": "  Más oscura  "})
    ).json()
    assert nota["texto"] == "Más oscura"
    assert (
        await c.post(url, json={"archivo": "a.png", "tipo": "nota", "texto": " "})
    ).status_code == 422
    assert (await c.post(url, json={"archivo": "otro.png", "tipo": "me_gusta"})).status_code == 422
    assert (await c.post(url, json={"archivo": "a.png", "tipo": "voto"})).status_code == 422
    a = (await c.get(f"/api/v1/tablero/entregas/{ID}")).json()["filas"][0]["archivos"][0]
    assert (a["me_gusta"], a["no_va"]) == (2, 1)
    assert [o["texto"] for o in a["opiniones"] if o["tipo"] == "nota"] == ["Más oscura"]
    assert (await c.get("/api/v1/tablero/entregas")).json()["entregas"][0]["opiniones"] == 4
    assert (await c.delete(f"/api/v1/tablero/opiniones/{nota['id']}")).status_code == 204
    assert (await c.delete(f"/api/v1/tablero/opiniones/{nota['id']}")).status_code == 404
    a = (await c.get(f"/api/v1/tablero/entregas/{ID}")).json()["filas"][0]["archivos"][0]
    assert len(a["opiniones"]) == 3
