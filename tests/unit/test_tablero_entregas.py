"""Spec-795: leer, validar y publicar las entregas del tablero (sin base ni API)."""

from datetime import date

import pytest
import yaml

from src.application.services.tablero import entregas as svc
from src.application.services.tablero.config import tablero_config
from src.domain.tablero import tipo_medio
from tests.support.tablero import entrega


def _yaml(carpeta, **cambios):
    datos = yaml.safe_load((carpeta / "entrega.yaml").read_text())
    datos.update(cambios)
    (carpeta / "entrega.yaml").write_text(yaml.safe_dump(datos, allow_unicode=True))


def test_lee_una_entrega_valida(tmp_path):
    e = svc.leer(entrega(tmp_path))
    assert e.id == "2026-11-26-calabaza-hoja"
    assert e.fecha == date(2026, 11, 26)  # sin fecha en el YAML: la del nombre
    assert [a.archivo for a in e.archivos()] == ["a.png", "b.png", "vistas.svg"]


def test_sin_filas_alcanza_con_sueltas(tmp_path):
    c = entrega(tmp_path, filas=[])
    assert [a.archivo for a in svc.leer(c).archivos()] == ["vistas.svg"]


def test_fecha_del_yaml_manda(tmp_path):
    c = entrega(tmp_path, fecha="2026-11-20")
    assert svc.leer(c).fecha == date(2026, 11, 20)


@pytest.mark.parametrize(
    ("cambio", "clave"),
    [
        ({"imagenes": [{"archivo": "no_esta.png"}]}, "Falta «no_esta.png»"),
        ({"imagenes": [{"archivo": "../stories.db"}]}, "no es un nombre"),
        ({"imagenes": [{"archivo": "sub/a.png"}]}, "no es un nombre"),
        ({"imagenes": [{"archivo": ".oculto.png"}]}, "no es un nombre"),
        ({"imagenes": [{"archivo": "a.png"}]}, "dos veces"),
        ({"filas": [], "imagenes": []}, "ningún archivo"),
        ({"titulo": ""}, "no se puede leer"),
    ],
)
def test_entregas_invalidas(tmp_path, cambio, clave):
    c = entrega(tmp_path)
    _yaml(c, **cambio)
    with pytest.raises(svc.EntregaInvalidaError, match=clave):
        svc.leer(c)


def test_extension_no_permitida(tmp_path):
    c = entrega(tmp_path)
    (c / "x.exe").write_bytes(b"MZ")
    _yaml(c, imagenes=[{"archivo": "x.exe"}])
    with pytest.raises(svc.EntregaInvalidaError, match="tipo"):
        svc.leer(c)


def test_tope_de_tamano(tmp_path, monkeypatch):
    c = entrega(tmp_path)
    monkeypatch.setattr(tablero_config(), "tope_mb_por_archivo", 0.000001)
    with pytest.raises(svc.EntregaInvalidaError, match="pesa más"):
        svc.leer(c)


def test_nombre_de_carpeta_raro(tmp_path):
    c = entrega(tmp_path, id_="Calabaza Hoja")
    with pytest.raises(svc.EntregaInvalidaError, match="AAAA-MM-DD"):
        svc.leer(c)


def test_leer_todas_saltea_las_invalidas_y_ordena(tmp_path):
    entrega(tmp_path, "2026-11-20-vieja")
    entrega(tmp_path, "2026-11-26-nueva")
    rota = entrega(tmp_path, "2026-11-25-rota")
    (rota / "a.png").unlink()
    (tmp_path / ".2026-11-27-x.tmp").mkdir()  # una publicación a medias no aparece
    buenas, malas = svc.leer_todas(tmp_path)
    assert [e.id for e in buenas] == ["2026-11-26-nueva", "2026-11-20-vieja"]
    assert [m.id for m in malas] == ["2026-11-25-rota"]


def test_ruta_solo_de_lo_declarado(tmp_path):
    c = entrega(tmp_path)
    (c / "secreto.png").write_bytes(b"x")
    e = svc.leer(c)
    assert svc.ruta_de(e, "a.png", tmp_path) == c / "a.png"
    assert svc.ruta_de(e, "secreto.png", tmp_path) is None
    assert svc.ruta_de(e, "entrega.yaml", tmp_path) is None


def test_publicar_copia_solo_lo_declarado_y_no_pisa(tmp_path):
    origen = entrega(tmp_path / "origen")
    (origen / "borrador.psd").write_bytes(b"x")
    base = tmp_path / "tablero"
    svc.publicar(origen, base)
    copiados = sorted(p.name for p in (base / origen.name).iterdir())
    assert copiados == ["a.png", "b.png", "entrega.yaml", "vistas.svg"]
    with pytest.raises(svc.EntregaInvalidaError, match="--reemplazar"):
        svc.publicar(origen, base)
    _yaml(origen, titulo="Otra")
    assert svc.publicar(origen, base, reemplazar=True).titulo == "Otra"
    assert [p.name for p in base.iterdir()] == [origen.name]  # sin temporales


def test_publicar_valida_antes_de_copiar(tmp_path):
    origen = entrega(tmp_path / "origen")
    (origen / "a.png").unlink()
    with pytest.raises(svc.EntregaInvalidaError):
        svc.publicar(origen, tmp_path / "tablero")
    assert not (tmp_path / "tablero").exists()


def test_tipo_medio():
    assert tipo_medio("voz.MP3") == "audio"
    assert tipo_medio("clip.mp4") == "video"
    assert tipo_medio("hoja.svg") == "imagen"
