"""Spec-530 S1: dominio del asistente de autoría (dirección, taller, escaleta).

Aditivo: las historias del wizard no cambian, y lo nuevo sobrevive a editar la
historia y al round-trip export-yaml → DB nueva → import-yaml.
"""

import uuid
from pathlib import Path

import pytest
import yaml

from src.application.dto import StoryCreateDTO
from src.application.use_cases.create_story import CreateStoryUseCase
from src.cli import commands
from src.config import settings
from src.domain.exceptions import InvalidAuthoringError
from src.domain.models import (
    ActOutline,
    CriterionStatus,
    Direction,
    Story,
    WorkshopItem,
    WorkshopLevel,
)
from src.infrastructure.database.connection import connection, init_db
from src.infrastructure.database.repositories import SQLStoryRepository
from src.infrastructure.exporters import YamlStoryExporter

INPUT_STORIES = Path(__file__).resolve().parents[2] / "input_stories"

_DIRECTION = {
    "premise": "Un chofer ve por el espejo a una mujer que murió en su micro.",
    "effect": "pavor",
    "ending": "El alma descansa en paz después de las flores.",
    "ending_intentional": True,
    "telling": "caso",
}
_WORKSHOP = [
    {
        "criterion": "meta",
        "status": "cumple",
        "answer": "Llegar antes del amanecer: su hija está internada.",
    },
    {
        "criterion": "vulnerabilidad",
        "status": "falta",
        "question": "¿Qué hace o cree José que lo deja expuesto?",
        "options": ["Se burla de los casos", "Maneja cansado", "No paró aquella noche"],
        "round": 2,
        "asked": ["¿Por qué a José?"],
    },
    {"criterion": "final", "status": "intencional", "answer": "Descansa en paz."},
]
_OUTLINE = [
    {
        "number": n,
        "goal": f"Meta del acto {n}",
        "events": [f"Hecho {n}.1", f"Hecho {n}.2"],
        "change_from": "antes",
        "change_to": "después",
        "scenario": "La ruta de noche",
        "on_stage": ["José", "El sereno"] if n == 1 else ["José"],
        "held_back": "El secreto" if n < 4 else "",
        "seeds": ["El ramo"] if n == 1 else [],
        "payoffs": ["El ramo"] if n == 4 else [],
        "decisions": ["meta"],
        "warnings": ["Aviso"] if n == 2 else [],
    }
    for n in range(1, 6)
]
_PERSONAJES = [
    {"id": "P1", "name": "José", "role": "Chofer", "traits": []},
    {"id": "P2", "name": "El sereno", "role": "", "kind": "sin_nombre", "relation": "Lo conozco"},
    {"id": "P3", "name": "Los compañeros", "role": "", "kind": "grupo", "relation": "Choferes"},
]


def _dto(**extra) -> StoryCreateDTO:
    base = {
        "title": "La pena del colectivo",
        "protagonista": "José: chofer",
        "relator": "Primera persona. Narrador: José.",
        "sinopsis": "José maneja de noche.",
        "personajes_full": _PERSONAJES,
        "typed_rules": [
            {"content": "Solo aparece cuando José está solo", "applies_to_beat": 2},
            {"content": "Regla global"},
        ],
        "direction": _DIRECTION,
        "workshop": _WORKSHOP,
        "outline": _OUTLINE,
    }
    return StoryCreateDTO(**{**base, **extra})


@pytest.fixture
async def db(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'db.db'}")
    await init_db()


@pytest.fixture
def repo() -> SQLStoryRepository:
    return SQLStoryRepository()


async def _create(repo, **extra) -> Story:
    story = await CreateStoryUseCase(repo).execute(_dto(**extra))
    return await repo.get_by_id(story.id)


# ── Alta y carga ────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("db")
async def test_alta_guarda_y_carga_direccion_taller_y_escaleta(repo):
    story = await _create(repo)

    assert story.direction == Direction(**_DIRECTION)
    assert [(w.criterion, w.status) for w in story.workshop] == [
        ("meta", CriterionStatus.CUMPLE),
        ("vulnerabilidad", CriterionStatus.FALTA),
        ("final", CriterionStatus.INTENCIONAL),
    ]
    assert story.workshop[1].options[2] == "No paró aquella noche"
    assert story.workshop[1].asked == ["¿Por qué a José?"]
    assert [a.number for a in story.outline] == [1, 2, 3, 4, 5]
    assert story.outline[0] == ActOutline(**_OUTLINE[0])


@pytest.mark.usefixtures("db")
async def test_personajes_con_tipo_y_relacion(repo):
    story = await _create(repo)

    assert [(p["name"], p["kind"], p["relation"]) for p in story.personajes_full] == [
        ("José", "persona", ""),
        ("El sereno", "sin_nombre", "Lo conozco"),
        ("Los compañeros", "grupo", "Choferes"),
    ]


@pytest.mark.usefixtures("db")
async def test_las_reglas_conservan_el_acto(repo):
    story = await _create(repo)

    assert story.active_rules_for_beat(2) == ["Solo aparece cuando José está solo", "Regla global"]
    assert story.active_rules_for_beat(3) == ["Regla global"]


@pytest.mark.usefixtures("db")
async def test_historia_del_wizard_queda_sin_autoria(repo):
    story = await _create(repo, direction=None, workshop=[], outline=[])

    assert story.direction is None
    assert story.workshop == []
    assert story.outline == []


# ── Escritura parcial ───────────────────────────────────────────────────────


@pytest.mark.usefixtures("db")
async def test_update_direction(repo):
    story = await _create(repo, direction=None)

    await repo.update_direction(story.id, Direction(premise="Otra", effect="susto"))

    assert (await repo.get_by_id(story.id)).direction == Direction(premise="Otra", effect="susto")


@pytest.mark.usefixtures("db")
async def test_el_taller_actualiza_el_criterio_sin_duplicarlo(repo):
    story = await _create(repo)

    await repo.save_workshop_items(
        story.id,
        [
            WorkshopItem(criterion="vulnerabilidad", status="cumple", answer="No paró.", round=3),
            WorkshopItem(level=WorkshopLevel.ESCALETA, criterion="escalada", status="parcial"),
        ],
    )

    items = {(w.level, w.criterion): w for w in await repo.get_workshop(story.id)}
    assert len(items) == 4
    vuln = items[(WorkshopLevel.DIRECCION, "vulnerabilidad")]
    assert (vuln.status, vuln.answer, vuln.round) == (CriterionStatus.CUMPLE, "No paró.", 3)
    assert items[(WorkshopLevel.ESCALETA, "escalada")].status == CriterionStatus.PARCIAL


@pytest.mark.usefixtures("db")
async def test_save_act_actualiza_un_acto_y_save_outline_reemplaza_todo(repo):
    story = await _create(repo)

    await repo.save_act(story.id, ActOutline(number=3, events=["Nuevo hecho"], needs_review=True))
    outline = await repo.get_outline(story.id)
    assert len(outline) == 5
    assert (outline[2].events, outline[2].needs_review, outline[2].goal) == (
        ["Nuevo hecho"],
        True,
        "",
    )

    await repo.save_outline(story.id, [ActOutline(number=1), ActOutline(number=2)])
    assert [a.number for a in await repo.get_outline(story.id)] == [1, 2]


@pytest.mark.usefixtures("db")
async def test_editar_la_historia_no_borra_la_autoria(repo):
    """`update_inputs` (edición desde el wizard) no manda dirección ni escaleta."""
    story = await _create(repo)
    edited = story.model_copy(
        update={"title": "Editada", "direction": None, "workshop": [], "outline": []}
    )

    await repo.update_inputs(edited)

    reloaded = await repo.get_by_id(story.id)
    assert reloaded.title == "Editada"
    assert reloaded.direction == Direction(**_DIRECTION)
    assert len(reloaded.workshop) == 3
    assert len(reloaded.outline) == 5


@pytest.mark.usefixtures("db")
async def test_borrar_la_historia_borra_la_autoria(repo):
    story = await _create(repo)

    await repo.delete(story.id)

    async with connection() as conn:
        for table in ("story_workshop", "act_outline"):
            cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
            assert (await cursor.fetchone())[0] == 0


# ── Validación ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("extra", "mensaje"),
    [
        ({"outline": [{"number": 6}]}, r"escaleta, elemento 1 \(number\)"),
        ({"outline": [{"number": 1}, {"number": 1}]}, "repite un número de acto"),
        (
            {"workshop": [{"criterion": "meta", "status": "verde"}]},
            r"taller, elemento 1 \(status\)",
        ),
        ({"personajes_full": [{"name": "X", "kind": "robot"}]}, "Tipo de personaje inválido"),
    ],
)
@pytest.mark.usefixtures("db")
async def test_autoria_invalida(repo, extra, mensaje):
    with pytest.raises(InvalidAuthoringError, match=mensaje):
        await CreateStoryUseCase(repo).execute(_dto(**extra))


# ── YAML ────────────────────────────────────────────────────────────────────


async def test_round_trip_yaml_conserva_la_autoria(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'a.db'}")
    await init_db()
    repo = SQLStoryRepository()
    before = await _create(repo)

    await commands._export_all_yaml_async(tmp_path / "yaml")
    (path,) = sorted((tmp_path / "yaml").glob("*.yaml"))
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["direction"]["effect"] == "pavor"
    assert doc["personajes_full"][2]["kind"] == "grupo"
    assert doc["storyteller_config"]["rules"][0]["applies_to_beat"] == 2

    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'b.db'}")
    assert await commands._import_yaml_async([path], drop_invalid_subgenre=False) == 0
    (summary,) = await repo.list_all()
    after = await repo.get_by_id(summary.id)

    assert after.direction == before.direction
    assert after.workshop == before.workshop
    assert after.outline == before.outline
    assert after.personajes_full == before.personajes_full
    assert after.active_rules_for_beat(2) == before.active_rules_for_beat(2)
    assert after.id != before.id and isinstance(after.id, uuid.UUID)


@pytest.mark.parametrize("name", ["el_monte_prohibido.yaml", "la_ofrenda.yaml"])
async def test_yaml_viejo_se_exporta_sin_claves_nuevas(monkeypatch, tmp_path, name):
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'db.db'}")
    await init_db()
    assert await commands._import_yaml_async([INPUT_STORIES / name], False) == 0
    (summary,) = await SQLStoryRepository().list_all()
    story = await SQLStoryRepository().get_by_id(summary.id)

    doc = YamlStoryExporter()._build_document(story)

    assert not {"direction", "workshop", "outline"} & doc.keys()
    assert all({"kind", "relation"}.isdisjoint(p) for p in doc["personajes_full"])
    assert all("applies_to_beat" not in r for r in doc["storyteller_config"]["rules"])
