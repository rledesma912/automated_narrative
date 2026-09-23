"""Spec-440 T2.4: `export-yaml --all` → DB nueva → `import-yaml` sin LLM.

Es el camino de recarga de las bases cuando cambia el esquema (sin scripts de
migración): tiene que conservar todo lo que el autor cargó.
"""

from pathlib import Path

import httpx
import pytest
import yaml

from src.cli import commands
from src.config import settings
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLStoryRepository
from src.infrastructure.exporters import YamlStoryExporter
from src.main import app

_ACTOS = {f"act_{n}": {"type": "exposicion", "text": f"Acto {n}: algo pasa."} for n in range(1, 6)}

_PAYLOAD = {
    "title": "Round trip",
    "protagonista": "Rosa: peona",
    "relator": "Primera persona en pasado. Narrador: Rosa. Registro: rural_tradicional.",
    "escenarios": "El galpón: chapas",
    "sinopsis": "\n\n".join(a["text"] for a in _ACTOS.values()),
    "genero": "folk_horror",
    "subgenero": "brujeria",
    "tono": "opresivo",
    "reglas": ["Nadie entra de noche", "Los perros no ladran"],
    "narrator_config": {
        "storyteller_id": "P1",
        "voice_style": "intimista",
        "atmosphere": {"genre": "folk_horror", "subgenre": "brujeria", "tone": "opresivo"},
        "scenarios": [
            {"id": "S1", "order": 1, "name": "El galpón", "description": "chapas"},
            {"id": "S2", "order": 2, "name": "El monte", "description": "espinillos"},
        ],
        "rules": [
            {"id": "R1", "text": "Nadie entra de noche", "type": "fenomeno"},
            {"id": "R2", "text": "Los perros no ladran", "type": "social"},
        ],
        "actos": _ACTOS,
        "perception": {"reliability": "poco_confiable"},
        "language": {"register": "rural_tradicional", "figurative_density": "media"},
    },
    "personajes_full": [
        {"id": "P1", "name": "Rosa", "role": "peona", "traits": ["valiente"]},
        {"id": "P2", "name": "Tito", "role": "capataz", "traits": []},
    ],
}


def _use_db(monkeypatch, path: Path) -> None:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{path}")


async def _authoring_views() -> dict[str, dict]:
    """Vista de autoría (lo que ve el wizard) de cada historia, por título."""
    repo = SQLStoryRepository()
    exporter = YamlStoryExporter()
    out = {}
    for summary in await repo.list_all():
        story = await repo.get_by_id(summary.id)
        out[story.title] = {
            "genero": story.genero,
            "subgenero": story.subgenero,
            "tono": story.tono,
            "status": story.status.value,
            "personajes": story.personajes_full,
            "config": exporter.authoring_config(story),
        }
        # Los ids de regla son PK globales (UUID): se regeneran al importar.
        for rule in out[story.title]["config"].get("rules", []):
            rule.pop("id", None)
    return out


async def test_round_trip_export_import_conserva_la_autoria(monkeypatch, tmp_path):
    _use_db(monkeypatch, tmp_path / "old.db")
    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/stories?action=save", json=_PAYLOAD)
        assert resp.status_code == 201, resp.text
    before = await _authoring_views()

    await commands._export_all_yaml_async(tmp_path / "yaml")
    files = sorted((tmp_path / "yaml").glob("*.yaml"))
    assert [f.name for f in files] == ["round_trip.yaml"]

    _use_db(monkeypatch, tmp_path / "new.db")
    assert await commands._import_yaml_async(files, drop_invalid_subgenre=False) == 0
    after = await _authoring_views()

    assert after == before
    config = after["Round trip"]["config"]
    assert [r["type"] for r in config["rules"]] == ["fenomeno", "entorno"]  # social → entorno
    assert [a["text"] for a in config["actos"].values()] == [a["text"] for a in _ACTOS.values()]


def _write_yaml(path: Path, genero: str, subgenero: str) -> Path:
    data = {
        "title": f"Historia {genero}/{subgenero}",
        "protagonista": "Rosa",
        "relator": "Primera persona",
        "sinopsis": "Algo pasa.",
        "storyteller_config": {"atmosphere": {"genre": genero, "subgenre": subgenero}},
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture
async def empty_db(monkeypatch, tmp_path):
    _use_db(monkeypatch, tmp_path / "db.db")
    await init_db()


@pytest.mark.usefixtures("empty_db")
async def test_par_invalido_sin_flag_no_se_importa(tmp_path, capsys):
    path = _write_yaml(tmp_path / "x.yaml", "horror_cosmico", "rural")

    assert await commands._import_yaml_async([path], drop_invalid_subgenre=False) == 1
    assert "no corresponde al género 'horror_cosmico'" in capsys.readouterr().out
    assert await SQLStoryRepository().list_all() == []


@pytest.mark.usefixtures("empty_db")
async def test_par_invalido_con_flag_descarta_el_subgenero(tmp_path, capsys):
    path = _write_yaml(tmp_path / "x.yaml", "horror_cosmico", "rural")

    assert await commands._import_yaml_async([path], drop_invalid_subgenre=True) == 0
    assert "se descarta el subgénero 'rural'" in capsys.readouterr().out
    (story,) = await SQLStoryRepository().list_all()
    assert (story.genero, story.subgenero, story.status.value) == ("horror_cosmico", "", "draft")


@pytest.mark.usefixtures("empty_db")
async def test_genero_inexistente_no_se_importa_ni_con_flag(tmp_path):
    path = _write_yaml(tmp_path / "x.yaml", "inventado", "rural")

    assert await commands._import_yaml_async([path], drop_invalid_subgenre=True) == 1


@pytest.mark.usefixtures("empty_db")
async def test_un_archivo_invalido_no_frena_a_los_demas(tmp_path):
    bad = _write_yaml(tmp_path / "bad.yaml", "body_horror", "rural")
    good = _write_yaml(tmp_path / "good.yaml", "body_horror", "contagio")

    assert await commands._import_yaml_async([bad, good], drop_invalid_subgenre=False) == 1
    assert [s.title for s in await SQLStoryRepository().list_all()] == [
        "Historia body_horror/contagio"
    ]
