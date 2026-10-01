"""Spec-610 T0.1: la configuración del paquete para el video se carga y se valida."""

import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.application.services.video.config import load_video_config, video_config

CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "video"


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    destino = tmp_path / "video"
    shutil.copytree(CONFIG_DIR, destino)
    return destino


def _editar(directory: Path, archivo: str, **cambios) -> None:
    path = directory / archivo
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.update(cambios)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_la_config_del_repo_carga():
    config = video_config()
    assert config.lectura.palabras_por_minuto == 150
    assert config.presentador.outro.cierra_con == "Buenas noches."
    assert len(config.presentador.ejemplos_outro) == 3
    assert set(config.biblia.mezcla) == {"imagen", "animacion", "video"}
    assert "no people" in config.biblia.estilo


def test_lector_propuesto_segun_quien_narra():
    lectores = video_config().lectores
    assert lectores.propuesto("mujer") == "Yael"
    assert lectores.propuesto("hombre") == "Lucas"
    assert lectores.propuesto("no_se_sabe") is None


def test_la_mezcla_tiene_que_sumar_uno(copia):
    _editar(copia, "biblia_visual.yaml", mezcla={"imagen": 0.5, "animacion": 0.5, "video": 0.5})
    with pytest.raises(ValidationError, match="sumar 1"):
        load_video_config(copia)


def test_la_mezcla_trae_los_tres_tipos(copia):
    _editar(copia, "biblia_visual.yaml", mezcla={"imagen": 0.6, "animacion": 0.4})
    with pytest.raises(ValidationError, match="imagen, animacion y video"):
        load_video_config(copia)


def test_la_propuesta_tiene_que_ser_un_lector_que_lee_esa_voz(copia):
    _editar(copia, "lectores.yaml", propuesta={"mujer": "Lucas"})
    with pytest.raises(ValidationError, match="Lucas no lee"):
        load_video_config(copia)
    _editar(copia, "lectores.yaml", propuesta={"mujer": "Juana"})
    with pytest.raises(ValidationError, match="no es un lector"):
        load_video_config(copia)


def test_rango_invertido(copia):
    _editar(copia, "lectura.yaml", episodio_minutos={"desde": 17, "hasta": 12})
    with pytest.raises(ValidationError, match="rango invertido"):
        load_video_config(copia)
