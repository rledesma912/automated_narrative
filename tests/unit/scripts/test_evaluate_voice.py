"""Spec-470 T0.3: el arnés de evaluación corre de punta a punta con el LLM simulado."""

import json
from pathlib import Path

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


async def test_input_importa_la_historia_con_su_escaleta(tmp_path, monkeypatch):
    """Spec-590 T0.2: con --input la historia entra con su escaleta y no se re-planifica."""
    from src.application.services.authoring.planner import OutlinePlanner

    async def no_planificar(*_a, **_k):
        raise AssertionError("con escaleta completa no se planifica")

    monkeypatch.setattr(OutlinePlanner, "plan", no_planificar)
    bosque = Path("input_stories/no_te_detengas_en_el_bosque.yaml")

    report = await run("bosque", ["sin", "con"], 1, tmp_path, mock=True, input_path=bosque)

    assert [(r["variante"], r["corrida"]) for r in report["relatos"]] == [("relato", 1)]
    assert report["historia"] == bosque.name
    assert narrator_of(load_story("relato", bosque)) == "Leonardo"
    assert "oraciones_cortadas_pct" in report["promedios"]["relato"]
    assert (tmp_path / "bosque" / "relato_1.txt").exists()


# ── Spec-480 T2.4: perfil híbrido, costo y confirmación ─────────────────────

HYBRID = "ollama-gemma3-12b-voz-sonnet5"


def _hybrid(monkeypatch):
    """El perfil híbrido ya no está en la configuración: se inyecta solo en el test."""
    import src.config as config
    from tests.integration.test_hybrid_profile import hybrid_profile

    monkeypatch.setitem(config._llm_core["profiles"], HYBRID, hybrid_profile())


def _fakes(monkeypatch):
    _hybrid(monkeypatch)
    from src.infrastructure.adapters import AnthropicAdapter
    from tests.support.fake_anthropic import FakeAnthropic, message
    from tests.support.recording_llm import RecordingLLM

    fake = FakeAnthropic([message("Prosa.", input_tokens=3000, output_tokens=800)])
    adapters = {"ollama": RecordingLLM(), "anthropic": AnthropicAdapter(client=fake)}
    monkeypatch.setattr(LLMFactory, "_single", staticmethod(lambda p: adapters[p]))
    return fake


async def test_proveedor_pago_sin_yes_no_genera_y_estima_el_costo(tmp_path, monkeypatch, capsys):
    fake = _fakes(monkeypatch)

    report = await run("hibrido", ["sin", "con"], 1, tmp_path, profile=HYBRID)

    assert report["abortado"] is True
    assert report["costo_estimado_usd"] == 0.26  # 2 relatos × ~US$ 0,13 (Sonnet 5.5, pensando poco)
    assert fake.messages.calls == []
    out = capsys.readouterr().out
    assert "--yes" in out and "['voz']" in out
    assert settings.active_profile_name == "ollama-gemma3-12b"  # perfil restaurado


async def test_con_yes_reporta_el_costo_real_por_relato(tmp_path, monkeypatch):
    fake = _fakes(monkeypatch)

    report = await run("hibrido", ["sin"], 1, tmp_path, profile=HYBRID, yes=True)

    assert len(fake.messages.calls) == 5  # la Voz, en Claude
    (relato,) = report["relatos"]
    assert relato["tokens"] == {"voz": [15000, 4000]}
    # 5 × (3000 × US$ 2 + 800 × US$ 10) / 1e6
    assert relato["costo_usd"] == 0.07
    assert report["costo_por_relato_usd"] == 0.07
    assert report["perfil"] == HYBRID
    assert settings.active_profile_name == "ollama-gemma3-12b"
