"""Spec-760 S1: los topes del asistente salen de config y un texto de más se rechaza con
un mensaje que se entiende (sin cortar nada)."""

from collections.abc import AsyncIterator

import httpx
import pytest

from src.application.services.authoring import catalog
from src.config import settings
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.factories import LLMFactory
from src.main import app

API = "/api/v1/authoring"
FORM = {
    "title": "La idea larga",
    "premise": "Lucía escucha a su padre gritar desde el auto.",
    "effect": "pavor",
    "telling": "caso",
    "protagonist_name": "Lucía",
}
TOPES = catalog.topes()


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


async def _create(client, **extra) -> str:
    resp = await client.post(f"{API}/stories", json={**FORM, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()["story_id"]


async def test_las_opciones_traen_los_topes(client):
    data = (await client.get(f"{API}/options")).json()
    assert data["topes"] == TOPES
    assert data["topes"]["premise"] == 20000


async def test_una_idea_de_20000_entra_entera(client):
    """D1: la idea de 20 000 caracteres se guarda entera (con acentos: son más bytes)."""
    idea = ("Lucía oyó el auto frenar acá. " * 700)[: TOPES["premise"]]
    assert len(idea) == 20000
    sid = await _create(client)
    resp = await client.put(f"{API}/stories/{sid}/direction", json={**FORM, "premise": idea})
    assert resp.status_code == 200, resp.text
    state = (await client.get(f"{API}/stories/{sid}")).json()
    assert state["direction"]["premise"] == idea.strip()


async def test_una_idea_de_mas_se_rechaza_con_un_mensaje_claro(client):
    sid = await _create(client)
    idea = "a" * 21300
    resp = await client.put(f"{API}/stories/{sid}/direction", json={**FORM, "premise": idea})
    assert resp.status_code == 422
    assert resp.json()["detail"] == (
        "Este texto tiene 21.300 letras y entran hasta 20.000: acortalo un poco para que se guarde."
    )
    # No se guardó nada recortado.
    state = (await client.get(f"{API}/stories/{sid}")).json()
    assert state["direction"]["premise"] == FORM["premise"]


async def test_un_hecho_de_700_entra_y_uno_de_mas_no(client):
    """§1.2: los hechos se cortaban a los 400 caracteres en la pantalla."""
    sid = await _create(client)
    largo = "x" * 700
    resp = await client.put(f"{API}/stories/{sid}/outline/1", json={"events": [largo]})
    assert resp.status_code == 200, resp.text
    act = next(a for a in resp.json()["outline"]["acts"] if a["number"] == 1)
    assert act["events"] == [largo]
    resp = await client.put(
        f"{API}/stories/{sid}/outline/1", json={"events": ["x" * (TOPES["event"] + 1)]}
    )
    assert resp.status_code == 422
    assert "entran hasta 800" in resp.json()["detail"]


async def test_un_acto_con_nueve_hechos_se_puede_editar(client):
    """§1.3: la larga pide 9 hechos en el acto 3 y en prod hay cortos con 9: con el tope
    de 8 de antes, editar ese acto daba 422."""
    sid = await _create(client, structure="largo")
    hechos = [f"Hecho {i}" for i in range(1, 10)]
    resp = await client.put(f"{API}/stories/{sid}/outline/3", json={"events": hechos})
    assert resp.status_code == 200, resp.text
    resp = await client.put(
        f"{API}/stories/{sid}/outline/3", json={"events": ["h"] * (TOPES["events"] + 1)}
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == (
        f"Acá entran hasta {TOPES['events']} y hay {TOPES['events'] + 1}: "
        "sacá alguno para que se guarde."
    )


async def test_el_final_admite_lo_que_entra_en_la_idea(client):
    """B: el final sale recortado de la idea (Spec-690); una respuesta común sigue en 2 000."""
    sid = await _create(client)
    final = "Lucía no se asoma a la ventana. " * 160  # ~5 000
    resp = await client.patch(
        f"{API}/stories/{sid}/workshop/final", json={"action": "answer", "text": final}
    )
    assert resp.status_code == 200, resp.text
    resp = await client.patch(
        f"{API}/stories/{sid}/workshop/meta",
        json={"action": "answer", "text": "y" * (TOPES["answer"] + 1)},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"].startswith("Este texto tiene 2.001 letras y entran hasta 2.000")


async def test_otros_errores_de_validacion_siguen_como_siempre(client):
    resp = await client.post(f"{API}/stories", json={**FORM, "title": ""})
    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], list)
