"""Spec-680: recursos gastados (`config/recursos_gastados.yaml`) y los gestos que evita la Voz."""

import pytest

from src.application.services import recursos_gastados as rg
from src.application.services.authoring.outline_narrator import OutlineNarrator
from tests.unit.application.authoring.test_voice_prompts_snapshot import _story

MATE = next(g for g in rg.gestos() if g.id == "mate")


def test_el_archivo_carga_con_ids_unicos():
    assert rg.hechos() and rg.gestos()
    for kind in (rg.hechos(), rg.gestos()):
        assert len({r.id for r in kind}) == len(kind)
        assert all(r.nombre and r.detecta for r in kind)


@pytest.mark.parametrize(
    "texto",
    [
        "me cebé un mate",
        "tomaba mate en la garita",
        "el termo estaba frío",
        "un mate amargo",
    ],
)
def test_el_mate_se_detecta(texto):
    assert MATE.en(texto)


@pytest.mark.parametrize(
    "texto",
    ["tenía miedo de que me mate", "lo mate a palos", "un color mate", "olía a yerba y a kerosene"],
)
def test_matar_no_es_el_mate(texto):
    """D18: por raíz, «mate» y «matar» serían lo mismo."""
    assert MATE.en(texto) is None


@pytest.mark.parametrize(
    ("recurso", "texto"),
    [
        ("huellas", "En el barro hay huellas enormes."),
        ("perros", "Los perros del vecino ladran sin parar."),
        ("sombra", "Una sombra enorme cruza el patio."),
        ("ojos", "Entre los árboles brillan dos ojos."),
        ("golpes", "Golpean tres veces la puerta a las tres."),
        ("luz", "La luz de la cocina parpadea."),
        ("silencio_animales", "Los grillos se callaron de golpe."),
    ],
)
def test_los_hechos_de_manual_se_detectan(recurso, texto):
    assert next(r for r in rg.hechos() if r.id == recurso).en(texto)


def _con_hecho(texto: str):
    story = _story()
    acts = [story.outline[0].model_copy(update={"events": [texto]}), *story.outline[1:]]
    return story.model_copy(update={"outline": acts})


def test_lo_del_autor_sin_los_actos():
    """D19: los hechos de los actos los arma el Planificador: no cuentan como del autor."""
    story = _con_hecho("José encuentra huellas enormes.")
    assert "huellas" not in rg.author_text(story)
    assert "José ve por el espejo" in rg.author_text(story)


def test_la_voz_evita_el_mate_salvo_que_lo_traiga_la_historia():
    narrator = OutlineNarrator(llm=None)
    story = _story()
    system, _ = narrator.voice_prompts(story, story.outline[0], None)
    assert (
        "Gestos que ya se vieron en muchos relatos (no los uses; buscá otros): tomar mate" in system
    )
    con_mate = _con_hecho("José se ceba un mate antes de arrancar.")
    system, _ = narrator.voice_prompts(con_mate, con_mate.outline[0], None)
    assert "Gestos que ya se vieron" not in system
    assert "costumbres típicas de un país" in system


def test_la_guia_pide_no_enumerar_siempre_de_a_tres():
    system, _ = OutlineNarrator(llm=None).voice_prompts(_story(), _story().outline[0], None)
    assert "No describas ni enumeres siempre de a tres" in system
