"""Spec-450 S1: entidades narrativas — dominio, persistencia y API."""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest

from src.application.use_cases.create_story import build_entities
from src.config import settings
from src.domain.exceptions import InvalidEntityError
from src.domain.models import RevealLevel, Story
from src.infrastructure.database.connection import get_connection, init_db
from src.infrastructure.database.repositories import SQLStoryRepository
from src.main import app

_BASE = {
    "title": "t",
    "protagonista": "Rosa",
    "relator": "Primera persona",
    "escenarios": "",
    "sinopsis": "Algo pasa.",
    "genero": "folk_horror",
    "subgenero": "rural",
}
_MALA_HORA = {
    "name": "La Mala Hora",
    "nature": "folklorica",
    "description": "Aparece a la siesta",
    "manifestations": "Olor a azufre",
    "limits": "No cruza el agua",
    "reveal_level": "progresiva",
}


def _body(*entities: dict, **overrides) -> dict:
    return {**_BASE, **overrides, "narrator_config": {"entities": list(entities)}}


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'e.db'}")
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _entities(client, story_id: str) -> list[dict]:
    story = (await client.get(f"/api/v1/stories/{story_id}")).json()
    return story["storyteller_config"]["entities"]


# ── Dominio (T1.1) ───────────────────────────────────────────────────────────


class TestBuildEntities:
    def test_la_primera_es_la_principal_y_el_nivel_por_defecto_es_insinuada(self):
        sid = uuid4()
        entities = build_entities(sid, [{"nature": "culto"}, _MALA_HORA])
        story = Story(title="t", protagonista="p", relator="r", sinopsis="s", entities=entities)

        assert story.principal_entity.nature_id == "culto"
        assert [e.order_index for e in entities] == [0, 1]
        assert entities[0].reveal_level is RevealLevel.INSINUADA
        assert entities[1].reveal_level is RevealLevel.PROGRESIVA

    def test_sin_entidades_no_hay_principal(self):
        story = Story(title="t", protagonista="p", relator="r", sinopsis="s")
        assert story.principal_entity is None

    def test_mas_de_3_es_error(self):
        with pytest.raises(InvalidEntityError, match="hasta 3 entidades \\(llegaron 4\\)"):
            build_entities(uuid4(), [{"nature": "culto"}] * 4)

    @pytest.mark.parametrize(
        ("raw", "message"),
        [
            ({"nature": "culto", "name": "x" * 61}, "Entidad 1: «Nombre» supera los 60"),
            ({"nature": "culto", "description": "x" * 401}, "«Descripción» supera los 400"),
            ({"nature": "culto", "limits": "x" * 301}, "«Límites» supera los 300"),
            ({"name": "Sin naturaleza"}, "Entidad 1: falta «Naturaleza»"),
            ({"nature": "culto", "reveal_level": "a_veces"}, "«Nivel de revelación» no es válido"),
        ],
    )
    def test_campos_invalidos_con_mensaje_legible(self, raw, message):
        with pytest.raises(InvalidEntityError, match=message):
            build_entities(uuid4(), [raw])

    def test_recorta_espacios(self):
        (e,) = build_entities(uuid4(), [{"nature": " culto ", "name": "  Ellos "}])
        assert (e.nature_id, e.name) == ("culto", "Ellos")


# ── API + persistencia (T1.2, T1.3) ─────────────────────────────────────────


@pytest.mark.parametrize("count", [0, 1, 3])
async def test_alta_y_lectura_con_0_1_y_3_entidades(client, count):
    raws = [{**_MALA_HORA, "name": f"E{i}"} for i in range(count)]
    resp = await client.post("/api/v1/stories?action=save", json=_body(*raws))

    assert resp.status_code == 201, resp.text
    entities = await _entities(client, resp.json()["id"])
    assert [e["name"] for e in entities] == [f"E{i}" for i in range(count)]
    if count:
        assert entities[0] == {**_MALA_HORA, "name": "E0"}


async def test_narrator_config_persistido_no_duplica_las_entidades(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_body(_MALA_HORA))).json()[
        "id"
    ]
    story = (await client.get(f"/api/v1/stories/{story_id}")).json()
    assert "entities" not in (story["narrator_config"] or {})


@pytest.mark.parametrize(
    ("entities", "overrides", "detail"),
    [
        (
            [{"nature": "demonio"}],
            {"genero": "suspenso", "subgenero": ""},
            "Entidad 1: la naturaleza 'demonio' no corresponde al género 'suspenso'",
        ),
        (
            [{"nature": "inventada"}],
            {"genero": "", "subgenero": ""},
            "Entidad 1: la naturaleza 'inventada' no corresponde a ninguna del catálogo",
        ),
        ([{"nature": "culto"}] * 4, {}, "Una historia admite hasta 3 entidades (llegaron 4)"),
        (
            [{"nature": "culto"}, {"nature": "culto", "manifestations": "x" * 301}],
            {},
            "Entidad 2: «Manifestaciones» supera los 300 caracteres",
        ),
    ],
)
async def test_post_invalido_422(client, entities, overrides, detail):
    resp = await client.post("/api/v1/stories?action=save", json=_body(*entities, **overrides))

    assert resp.status_code == 422
    assert resp.json()["detail"] == detail


async def test_sin_genero_acepta_cualquier_naturaleza_del_catalogo(client):
    body = _body({"nature": "cosmica"}, genero="", subgenero="")
    assert (await client.post("/api/v1/stories?action=save", json=body)).status_code == 201


async def test_patch_reemplaza_las_entidades(client):
    story_id = (
        await client.post(
            "/api/v1/stories?action=save", json=_body(_MALA_HORA, {"nature": "culto"})
        )
    ).json()["id"]

    resp = await client.patch(f"/api/v1/stories/{story_id}", json=_body({"nature": "espiritu"}))

    assert resp.status_code == 200, resp.text
    assert [e["nature"] for e in await _entities(client, story_id)] == ["espiritu"]


async def test_patch_invalido_422_y_no_cambia_nada(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_body(_MALA_HORA))).json()[
        "id"
    ]

    body = _body({"nature": "demonio"}, genero="suspenso", subgenero="", title="otro")
    resp = await client.patch(f"/api/v1/stories/{story_id}", json=body)

    assert resp.status_code == 422
    story = (await client.get(f"/api/v1/stories/{story_id}")).json()
    assert story["title"] == "t"
    assert [e["name"] for e in story["storyteller_config"]["entities"]] == ["La Mala Hora"]


async def _journal_rows(story_id: str) -> list[tuple]:
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT beat_number, entity_state FROM entity_journal WHERE story_id = ?", (story_id,)
        )
        return [tuple(r) for r in await cursor.fetchall()]
    finally:
        await conn.close()


async def test_editar_no_borra_el_journal_de_entidades_y_borrar_la_historia_si(client):
    story_id = (await client.post("/api/v1/stories?action=save", json=_body(_MALA_HORA))).json()[
        "id"
    ]
    conn = await get_connection()
    await conn.execute(
        "INSERT INTO entity_journal (id, story_id, beat_number, entity_state) VALUES (?, ?, 1, ?)",
        (str(uuid4()), story_id, "La Mala Hora rondó el galpón"),
    )
    await conn.commit()
    await conn.close()

    await client.patch(f"/api/v1/stories/{story_id}", json=_body({"nature": "culto"}))
    assert await _journal_rows(story_id) == [(1, "La Mala Hora rondó el galpón")]

    await client.delete(f"/api/v1/stories/{story_id}")
    assert await _journal_rows(story_id) == []


async def test_list_all_carga_las_entidades(client):
    await client.post("/api/v1/stories?action=save", json=_body(_MALA_HORA))
    (story,) = await SQLStoryRepository().list_all()
    assert [e.name for e in story.entities] == ["La Mala Hora"]
    assert isinstance(story.entities[0].story_id, UUID)


# ── YAML (T1.4) ──────────────────────────────────────────────────────────────


def test_loader_yaml_lee_entidades_y_las_saca_del_narrator_config():
    from src.infrastructure.loaders import YamlStoryLoader

    dto = YamlStoryLoader().load(
        "title: t\nprotagonista: p\nrelator: r\nsinopsis: s\n"
        "storyteller_config:\n  voice_style: intimista\n"
        "  entities:\n    - {name: Ellos, nature: culto, reveal_level: nunca}\n"
    )
    assert dto.entities == [{"name": "Ellos", "nature": "culto", "reveal_level": "nunca"}]
    assert "entities" not in dto.narrator_config


def test_loader_yaml_sin_entidades():
    from src.infrastructure.loaders import YamlStoryLoader

    dto = YamlStoryLoader().load("title: t\nprotagonista: p\nrelator: r\nsinopsis: s\n")
    assert dto.entities == []
