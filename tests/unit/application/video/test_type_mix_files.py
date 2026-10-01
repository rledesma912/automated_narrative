"""Spec-610 T2.4: tipos al azar con semilla y nombres de archivo."""

import uuid

import pytest

from src.application.services.video import files, type_mix
from src.application.services.video.config import video_config

BIBLIA = video_config().biblia


@pytest.mark.parametrize("seed", range(40))
def test_reglas_de_la_mezcla(seed):
    strong = [False] * 12
    strong[5] = strong[9] = True
    tipos = type_mix.assign(strong, BIBLIA, seed)

    assert len(tipos) == 12
    assert BIBLIA.videos.desde <= tipos.count("video") <= BIBLIA.videos.hasta
    assert all(not (a == b == "video") for a, b in zip(tipos, tipos[1:], strict=False))
    assert tipos[5] == "video"  # el primer momento fuerte
    assert tipos[9] in ("video", "animacion")
    assert tipos.count("animacion") == round(12 * BIBLIA.mezcla["animacion"])


def test_misma_semilla_mismo_mapa_y_otra_semilla_otro():
    strong = [False] * 13
    a = type_mix.assign(strong, BIBLIA, 7)
    assert type_mix.assign(strong, BIBLIA, 7) == a
    assert any(type_mix.assign(strong, BIBLIA, s) != a for s in range(8, 20))


def test_la_semilla_sale_de_la_variante():
    narrative_id = uuid.UUID("1d6ff529-dbd0-44f7-a55e-9d2c55cb5879")
    assert type_mix.seed_for(narrative_id) == type_mix.seed_for(narrative_id)
    assert 0 <= type_mix.seed_for(narrative_id) < 2**31


def test_pocos_momentos():
    assert type_mix.assign([], BIBLIA, 1) == []
    assert type_mix.assign([True], BIBLIA, 1) == ["video"]
    tipos = type_mix.assign([False, False, False], BIBLIA, 1)
    assert tipos.count("video") == 1


@pytest.mark.parametrize(
    ("lugar", "esperado"),
    [
        ("Borde del bosque", "borde-del-bosque"),
        ("  El almacén ¡de noche!  ", "el-almacen-de-noche"),
        ("Ñandú", "nandu"),
        ("???", "momento"),
        ("una frase muy larga para un nombre de archivo", "una-frase-muy-larga-para-un"),
    ],
)
def test_slug(lugar, esperado):
    assert files.slug(lugar) == esperado


def test_nombres_de_archivo_en_orden():
    assert files.file_names(6, "Ventanilla", "video") == ["06-ventanilla.png", "06-ventanilla.mp4"]
    assert files.file_names(12, "Mostrador", "imagen") == ["12-mostrador.png"]
