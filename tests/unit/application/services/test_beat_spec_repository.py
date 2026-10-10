"""Tests para BeatSpecRepository — Spec 063 Slice A; Spec-650: estructuras."""

from pathlib import Path

import pytest
import yaml

from src.application.services.beat_spec_repository import BeatSpecRepository


def _write_yaml(tmp_path: Path, beats: list[dict], **extra) -> Path:
    textos = {"palabras_total": "2.500", "hechos_por_acto": "de 3 a 5 hechos"}
    largo = {"label": "Largo", "revela_secreto": 4, "actos": beats, **textos}
    if "corto" in extra:  # D10: tablas de reubicación entre las dos
        largo["reubicar_desde"] = {"corto": {1: 1, 2: 3, 3: 5}}
        extra["corto"].setdefault("reubicar_desde", {"largo": {1: 1, 2: 2, 3: 2, 4: 3, 5: 3}})
    data = {"beats_spec": {"estructuras": {"largo": largo, **extra}}}
    f = tmp_path / "beats.yaml"
    f.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return f


FIVE_BEATS = [
    {
        "id": 1,
        "name": "exposicion",
        "label": "exposicion",
        "nombre_ui": "Nombre exposicion",
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
        "label": "accion_ascendente",
        "nombre_ui": "Nombre accion_ascendente",
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
        "label": "climax",
        "nombre_ui": "Nombre climax",
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
        "label": "accion_descendente",
        "nombre_ui": "Nombre accion_descendente",
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
        "label": "desenlace",
        "nombre_ui": "Nombre desenlace",
        "intent": "cierre ambiguo",
        "intensity": "baja",
        "must": ["tension residual"],
        "must_not": ["explicar lo inexplicable"],
        "state_change": {"from": "resignacion", "to": "trauma latente"},
        "success_signal": ["lector queda inquieto"],
    },
]


class TestBeatSpecRepositoryLoad:
    def test_cinco_actos_en_la_larga(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))
        assert repo.estructura().num_actos == 5
        assert repo.estructura().ultimo == 5

    def test_get_all_retorna_lista(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))
        assert len(repo.get_all()) == 5

    def test_get_all_es_copia(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))
        lista = repo.get_all()
        lista.clear()
        assert repo.estructura().num_actos == 5

    def test_archivo_no_existe_es_error(self, tmp_path):
        """Spec-650: sin el YAML no hay actos que inventar (antes: 5 vacíos en silencio)."""
        with pytest.raises(FileNotFoundError):
            BeatSpecRepository(tmp_path / "no_existe.yaml")

    def test_yaml_sin_estructura_larga_es_error(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(yaml.dump({"otro": "valor"}), encoding="utf-8")
        with pytest.raises(ValueError, match="largo"):
            BeatSpecRepository(f)


class TestEstructuras:
    """Spec-650: varias estructuras; cada una se valida al cargar."""

    def _corto(self) -> dict:
        actos = [{**FIVE_BEATS[i], "id": i + 1, "palabras": [100, 200]} for i in range(3)]
        textos = {"palabras_total": "1.050", "hechos_por_acto": "los que pide cada acto,"}
        return {"label": "Corto", "revela_secreto": 2, "actos": actos, **textos}

    def test_estructura_pedida(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=self._corto()))
        corto = repo.estructura("corto")
        assert (corto.num_actos, corto.ultimo, corto.revela_secreto) == (3, 3, 2)
        assert corto.numeros == [1, 2, 3]
        assert corto.tiene(3) and not corto.tiene(4) and not corto.tiene(0)
        assert repo.get_by_id(3, structure="corto")["name"] == "climax"
        assert repo.get_by_id(4, structure="corto") == {}
        assert set(repo.structure_ids) == {"largo", "corto"}

    def test_estructura_desconocida_es_error_no_la_larga(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS))
        with pytest.raises(KeyError):
            repo.estructura("mediano")
        with pytest.raises(KeyError):
            repo.get_by_id(1, structure="mediano")

    def test_actos_fuera_de_orden_es_error(self, tmp_path):
        corto = self._corto()
        corto["actos"][1]["id"] = 5
        with pytest.raises(ValueError, match="1..N"):
            BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=corto))

    def test_acto_sin_nombre_para_la_ui_es_error(self, tmp_path):
        corto = self._corto()
        del corto["actos"][0]["nombre_ui"]
        with pytest.raises(ValueError, match="nombre_ui"):
            BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=corto))

    def test_revela_secreto_fuera_de_la_estructura_es_error(self, tmp_path):
        corto = {**self._corto(), "revela_secreto": 4}
        with pytest.raises(ValueError, match="revela_secreto"):
            BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=corto))

    def test_exposicion_desconocida_es_error(self, tmp_path):
        corto = self._corto()
        corto["actos"][0]["entity_exposure"] = {"nunca": "no_existe"}
        with pytest.raises(ValueError, match="exposición"):
            BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=corto))

    def test_reubicar_entre_estructuras(self, tmp_path):
        repo = BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=self._corto()))
        largo, corto = repo.estructura("largo"), repo.estructura("corto")
        assert [corto.reubicar(n, largo) for n in range(1, 6)] == [1, 2, 2, 3, 3]
        assert [largo.reubicar(n, corto) for n in range(1, 4)] == [1, 3, 5]
        assert largo.reubicar(4, largo) == 4

    def test_tabla_de_reubicacion_incompleta_es_error(self, tmp_path):
        corto = {**self._corto(), "reubicar_desde": {"largo": {1: 1, 2: 2, 3: 3}}}
        with pytest.raises(ValueError, match="reubicar_desde"):
            BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=corto))

    def test_reubicar_a_un_acto_que_no_existe_es_error(self, tmp_path):
        corto = {**self._corto(), "reubicar_desde": {"largo": {1: 1, 2: 2, 3: 2, 4: 3, 5: 4}}}
        with pytest.raises(ValueError, match="no existe"):
            BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=corto))

    def test_hechos_sin_tope_es_error(self, tmp_path):
        corto = self._corto()
        corto["actos"][0]["hechos"] = "2 o 3"
        with pytest.raises(ValueError, match="hechos_max"):
            BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=corto))

    def test_palabras_invertidas_es_error(self, tmp_path):
        corto = self._corto()
        corto["actos"][0]["palabras"] = [300, 200]
        with pytest.raises(ValueError, match="palabras"):
            BeatSpecRepository(_write_yaml(tmp_path, FIVE_BEATS, corto=corto))

    def test_el_yaml_real_trae_el_corto(self):
        """Spec-650 §2.1: 3 actos, 940–1 140 palabras (≈ 7 min a 150 por minuto)."""
        corto = BeatSpecRepository().estructura("corto")
        assert (corto.num_actos, corto.ultimo, corto.revela_secreto) == (3, 3, 2)
        assert [a["nombre_ui"] for a in corto.actos] == ["Cómo empieza", "Qué pasa", "Cómo termina"]
        assert sum(a["palabras"][0] for a in corto.actos) == 940
        assert sum(a["palabras"][1] for a in corto.actos) == 1140

    def test_el_yaml_real_carga_y_la_larga_tiene_cinco(self):
        repo = BeatSpecRepository()
        largo = repo.estructura()
        assert largo.num_actos == 5 and largo.revela_secreto == 4
        assert [a["nombre_ui"] for a in largo.actos] == [
            "Cómo empieza",
            "Se complica",
            "El peor momento",
            "Qué hace después",
            "Cómo termina",
        ]


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
