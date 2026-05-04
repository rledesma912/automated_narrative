"""Tests para BeatSpecRepository — Spec 063 Slice A."""

from pathlib import Path

import pytest
import yaml

from src.application.services.beat_spec_repository import BeatSpecRepository


def _write_yaml(tmp_path: Path, beats: list[dict]) -> Path:
    data = {"beats_spec": {"macro_beats": beats}}
    f = tmp_path / "beats.yaml"
    f.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return f


FIVE_BEATS = [
    {
        "id": 1,
        "name": "exposicion",
        "intent": "establecer normalidad",
        "intensity": "baja",
        "must": ["presentar situacion"],
        "must_not": ["confirmar paranormal"],
        "state_change": {"from": "estabilidad", "to": "incomodidad"},
        "success_signal": ["algo no encaja"],
    },
    {
        "id": 2,
        "name": "accion_ascendente",
        "intent": "activar conflicto",
        "intensity": "media",
        "must": ["romper la regla"],
        "must_not": ["aceptar paranormal"],
        "state_change": {"from": "incomodidad", "to": "alarma"},
        "success_signal": ["evento anomalo visible"],
    },
    {
        "id": 3,
        "name": "climax",
        "intent": "confrontacion con lo inexplicable",
        "intensity": "alta",
        "must": ["enfrentamiento directo"],
        "must_not": ["resolver el misterio"],
        "state_change": {"from": "alarma", "to": "terror"},
        "success_signal": ["punto de no retorno"],
    },
    {
        "id": 4,
        "name": "accion_descendente",
        "intent": "consecuencias",
        "intensity": "media",
        "must": ["mostrar secuelas"],
        "must_not": ["introducir personajes nuevos"],
        "state_change": {"from": "terror", "to": "resignacion"},
        "success_signal": ["personaje cambiado"],
    },
    {
        "id": 5,
        "name": "desenlace",
        "intent": "cierre ambiguo",
        "intensity": "baja",
        "must": ["tension residual"],
        "must_not": ["explicar lo inexplicable"],
        "state_change": {"from": "resignacion", "to": "trauma latente"},
        "success_signal": ["lector queda inquieto"],
    },
]


class TestBeatSpecRepositoryLoad:
    def test_num_beats_cinco(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))
        assert repo.num_beats == 5

    def test_get_all_retorna_lista(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))
        assert len(repo.get_all()) == 5

    def test_get_all_es_copia(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))
        lista = repo.get_all()
        lista.clear()
        assert repo.num_beats == 5

    def test_archivo_no_existe_usa_fallback(self, tmp_path):
        repo = BeatSpecRepository(tmp_path / "no_existe.yaml")
        assert repo.num_beats == 5
        assert repo.get_by_id(1)["name"] == "beat_1"

    def test_yaml_sin_clave_retorna_vacio(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(yaml.dump({"otro": "valor"}), encoding="utf-8")
        repo = BeatSpecRepository(f)
        assert repo.num_beats == 0


class TestBeatSpecRepositoryGetById:
    @pytest.fixture
    def repo(self, tmp_path):
        return BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))

    def test_get_by_id_exposicion(self, repo):
        b = repo.get_by_id(1)
        assert b["name"] == "exposicion"

    def test_get_by_id_climax(self, repo):
        b = repo.get_by_id(3)
        assert b["name"] == "climax"

    def test_get_by_id_desenlace(self, repo):
        b = repo.get_by_id(5)
        assert b["name"] == "desenlace"

    def test_get_by_id_no_existe(self, repo):
        assert repo.get_by_id(99) == {}


class TestBeatSpecRepositoryFormatCompact:
    @pytest.fixture
    def repo(self, tmp_path):
        return BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))

    def test_contiene_cinco_nombres(self, repo):
        text = repo.format_compact()
        for name in [
            "exposicion",
            "accion_ascendente",
            "climax",
            "accion_descendente",
            "desenlace",
        ]:
            assert name in text

    def test_contiene_intents(self, repo):
        text = repo.format_compact()
        assert "establecer normalidad" in text
        assert "cierre ambiguo" in text

    def test_cinco_lineas(self, repo):
        lines = repo.format_compact().splitlines()
        assert len(lines) == 5


class TestBeatSpecRepositoryFormatForBeat:
    @pytest.fixture
    def repo(self, tmp_path):
        return BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))

    def test_frontier_contiene_must(self, repo):
        text = repo.format_for_beat(1, variant="frontier")
        assert "presentar situacion" in text

    def test_frontier_contiene_must_not(self, repo):
        text = repo.format_for_beat(1, variant="frontier")
        assert "confirmar paranormal" in text

    def test_frontier_contiene_transicion(self, repo):
        text = repo.format_for_beat(1, variant="frontier")
        assert "estabilidad" in text
        assert "incomodidad" in text

    def test_compact_contiene_arco_emocional(self, repo):
        text = repo.format_for_beat(1, variant="compact")
        assert "Arco emocional" in text

    def test_compact_contiene_prohibido(self, repo):
        text = repo.format_for_beat(1, variant="compact")
        assert "PROHIBIDO" in text

    def test_compact_contiene_objetivo(self, repo):
        text = repo.format_for_beat(1, variant="compact")
        assert "Objetivo del fragmento" in text

    def test_beat_inexistente_retorna_vacio(self, repo):
        assert repo.format_for_beat(99) == ""

    def test_formato_por_defecto_es_frontier(self, repo):
        assert repo.format_for_beat(1) == repo.format_for_beat(1, variant="frontier")
