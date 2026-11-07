"""Spec-750 S2: la larga (~35 min) tiene los mismos 5 actos que la media, con más hechos
y más palabras por acto, y reusa sus textos (`textos_de: medio`) sin copiarlos."""

import pytest

from src.application.services.authoring import catalog, molde
from src.application.services.authoring.outline_narrator import word_range
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.domain.models import ActOutline
from tests.unit.application.services.test_beat_spec_repository import FIVE_BEATS, _write_yaml

REPO = BeatSpecRepository()
MEDIA, LARGA = REPO.estructura("medio"), REPO.estructura("largo")

# §3 de la spec: palabras y tope de hechos de cada acto.
PALABRAS = {1: (800, 950), 2: (1100, 1250), 3: (1200, 1350), 4: (1100, 1250), 5: (450, 550)}
HECHOS_MAX = {1: 6, 2: 8, 3: 9, 4: 8, 5: 4}


def test_los_tres_largos_y_sus_textos():
    assert set(REPO.structure_ids) == {"corto", "medio", "largo"}
    assert (LARGA.textos, MEDIA.textos, REPO.estructura("corto").textos) == (
        "medio",
        "medio",
        "corto",
    )


def test_la_larga_tiene_los_actos_de_la_media():
    assert LARGA.numeros == MEDIA.numeros == [1, 2, 3, 4, 5]
    assert LARGA.revela_secreto == MEDIA.revela_secreto
    assert LARGA.personajes_nuevos_max == MEDIA.personajes_nuevos_max
    for media, larga in zip(MEDIA.actos, LARGA.actos, strict=True):
        for key in ("name", "label", "nombre_ui", "intent", "intensity", "must", "must_not"):
            assert larga.get(key) == media.get(key), (larga["id"], key)
        assert larga["entity_exposure"] == media["entity_exposure"]
        assert larga.get("reveal_rules") == media.get("reveal_rules")


def test_la_larga_crece_en_hechos_y_palabras():
    for n in LARGA.numeros:
        assert tuple(LARGA.acto(n)["palabras"]) == PALABRAS[n]
        assert LARGA.acto(n)["hechos_max"] == HECHOS_MAX[n]
        assert word_range(ActOutline(number=n, events=["algo"]), LARGA) == PALABRAS[n]
    total = sum(hasta for _, hasta in PALABRAS.values())
    assert 5000 <= total <= 5400  # ~35 min a 150 palabras por minuto
    assert "35" in LARGA.label and LARGA.label.startswith("Larga · 5 actos")
    assert MEDIA.label.startswith("Media · 5 actos")


def test_reubicar_entre_media_y_larga_es_uno_a_uno():
    assert [LARGA.reubicar(n, MEDIA) for n in MEDIA.numeros] == MEDIA.numeros
    assert [MEDIA.reubicar(n, LARGA) for n in LARGA.numeros] == LARGA.numeros
    corto = REPO.estructura("corto")
    assert [LARGA.reubicar(n, corto) for n in corto.numeros] == [
        MEDIA.reubicar(n, corto) for n in corto.numeros
    ]


def test_los_efectos_y_los_criterios_de_la_larga_son_los_de_la_media():
    assert catalog.effects("largo") == catalog.effects("medio")
    assert catalog.criteria_bank("largo") == catalog.criteria_bank("medio")


@pytest.mark.parametrize("forma", [f.id for f in molde.catalogo().formas])
def test_cada_forma_pide_en_la_larga_lo_mismo_que_en_la_media(forma):
    f = molde.catalogo().forma(forma)
    media, larga = molde.Molde(f, None, "medio"), molde.Molde(f, None, "largo")
    for n in LARGA.numeros:
        assert larga.intencion(n, "x") == media.intencion(n, "x")
    assert larga.acto_revela(4) == media.acto_revela(4)


# ── Validación de `textos_de` ────────────────────────────────────────────────


def _con_textos(tmp_path, textos_de: str):
    otra = {
        "label": "Otra",
        "revela_secreto": 4,
        "actos": FIVE_BEATS,
        "palabras_total": "5.000",
        "hechos_por_acto": "muchos hechos",
        "textos_de": textos_de,
        "reubicar_desde": {"medio": {n: n for n in range(1, 6)}},
    }
    path = _write_yaml(tmp_path, FIVE_BEATS, otra=otra)
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["beats_spec"]["estructuras"]["medio"]["reubicar_desde"] = {
        "otra": {n: n for n in range(1, 6)}
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_textos_de_una_estructura_que_no_existe_es_error(tmp_path):
    with pytest.raises(ValueError, match="textos_de"):
        BeatSpecRepository(_con_textos(tmp_path, "nada"))


def test_textos_de_otra_que_a_su_vez_los_toma_prestados_es_error(tmp_path):
    with pytest.raises(ValueError, match="textos_de"):
        BeatSpecRepository(_con_textos(tmp_path, "otra"))  # se apunta a sí misma


def test_textos_de_la_media_carga(tmp_path):
    repo = BeatSpecRepository(_con_textos(tmp_path, "medio"))
    assert repo.estructura("otra").textos == "medio"
