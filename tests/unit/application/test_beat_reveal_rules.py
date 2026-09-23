"""Spec-450 T2.3: reglas de revelación y exposición de entidades por nivel."""

import pytest

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.domain.models import RevealLevel

CONFIRMAR = "confirmar lo paranormal"
ACEPTAR = "aceptar lo paranormal como hecho"
PRESENCIA = "mostrar amenaza o presencia directa"
ORIGEN = "explicar origen o reglas completas del fenomeno"


@pytest.fixture(scope="module")
def repo() -> BeatSpecRepository:
    return BeatSpecRepository()


def test_sin_nivel_es_la_variante_de_hoy(repo):
    assert repo.get_by_id(1)["must_not"] == [CONFIRMAR]
    assert repo.get_by_id(2)["must_not"] == [ACEPTAR]
    assert repo.get_by_id(3)["must"][-1] == PRESENCIA


def test_explicita_quita_los_must_not_de_los_beats_1_y_2(repo):
    assert repo.get_by_id(1, RevealLevel.EXPLICITA)["must_not"] == []
    assert repo.get_by_id(2, "explicita")["must_not"] == []
    assert PRESENCIA in repo.get_by_id(3, RevealLevel.EXPLICITA)["must"]


def test_nunca_cambia_la_presencia_del_beat_3_por_senales(repo):
    must = repo.get_by_id(3, RevealLevel.NUNCA)["must"]
    assert PRESENCIA not in must
    assert "mostrar señales intensas de la amenaza sin confirmar qué es" in must
    assert repo.get_by_id(1, RevealLevel.NUNCA)["must_not"] == [CONFIRMAR]


@pytest.mark.parametrize("level", list(RevealLevel))
def test_la_regla_de_origen_del_beat_3_queda_fija(repo, level):
    assert repo.get_by_id(3, level)["must_not"] == [ORIGEN]


@pytest.mark.parametrize("level", [RevealLevel.INSINUADA, RevealLevel.PROGRESIVA])
def test_niveles_sin_override_usan_default(repo, level):
    assert repo.get_all(level) == repo.get_all()


def test_el_beat_resuelto_no_expone_las_claves_internas(repo):
    beat = repo.get_by_id(1, RevealLevel.EXPLICITA)
    assert "reveal_rules" not in beat and "entity_exposure" not in beat


def test_format_for_beat_usa_el_nivel(repo):
    assert CONFIRMAR in repo.format_for_beat(1, "compact")
    assert CONFIRMAR not in repo.format_for_beat(1, "compact", RevealLevel.EXPLICITA)


@pytest.mark.parametrize(
    ("beat", "level", "key", "shows_name"),
    [
        (1, RevealLevel.NUNCA, "senales", False),
        (1, RevealLevel.EXPLICITA, "presencia", True),
        (3, RevealLevel.INSINUADA, "revelacion", True),
        (3, RevealLevel.PROGRESIVA, "presencia_directa", False),
        (5, RevealLevel.NUNCA, "segun_acto_5", True),
    ],
)
def test_exposicion_por_beat_y_nivel(repo, beat, level, key, shows_name):
    exposure = repo.exposure_for(beat, level)
    assert exposure["key"] == key
    assert exposure["guide"]
    assert ("name" in exposure["show"]) is shows_name


def test_cada_beat_define_los_4_niveles(repo):
    for beat in range(1, 6):
        for level in RevealLevel:
            assert repo.exposure_for(beat, level), (beat, level)
