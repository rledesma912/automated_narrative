"""Spec-470 T0.3: el arnés de evaluación corre de punta a punta con el LLM simulado."""

import json

from scripts.evaluate_voice import ENTITIES, load_story, narrator_of, run
from src.config import settings
from src.infrastructure.factories import LLMFactory


def test_historias_de_la_evaluacion():
    assert "entities" not in load_story("sin")["storyteller_config"]
    assert load_story("con")["storyteller_config"]["entities"] == ENTITIES
    assert narrator_of(load_story("sin")) == "Irene"


async def test_corre_con_mock_y_restaura_lo_que_parchea(tmp_path):
    db, provider = settings.database_url, LLMFactory.get_provider
    voz_before = settings.role_config("voz").get("temperature")

    report = await run("prueba", ["sin", "con"], 1, tmp_path, voz_temperature=0.5, mock=True)

    assert [(r["variante"], r["corrida"]) for r in report["relatos"]] == [("sin", 1), ("con", 1)]
    assert report["voz_temperature"] == 0.5
    assert set(report["promedios"]) == {"sin", "con"}
    saved = json.loads((tmp_path / "prueba" / "metrics.json").read_text("utf-8"))
    assert saved["relatos"][0]["palabras"] > 0
    assert (tmp_path / "prueba" / "con_1.txt").exists()
    # Todo lo parcheado vuelve a su lugar.
    assert (settings.database_url, LLMFactory.get_provider) == (db, provider)
    assert settings.role_config("voz").get("temperature") == voz_before
