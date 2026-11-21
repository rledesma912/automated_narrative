"""Spec-550 H7: los criterios del taller dicen de quién hablan y para qué sirven."""

import pytest

from src.application.services.authoring import catalog


def _by_id(protagonist: str) -> dict[str, catalog.Criterion]:
    return {c.id: c.for_story(protagonist) for c in catalog.direction_criteria()}


def test_nombres_con_el_protagonista():
    c = _by_id("José")
    assert c["meta"].nombre == "Qué quiere José"
    assert c["en_juego"].nombre == "Qué puede perder José"
    assert c["vulnerabilidad"].nombre == "En qué se equivoca José"
    assert c["transgresion"].nombre == "Lo que José no tendría que haber hecho"
    assert c["historia_secreta"].nombre == "Lo que esconde la historia"
    assert c["descubrimiento"].nombre == "Lo que descubre José"
    assert c["reaccion"].nombre == "Qué hace José después"
    assert c["final"].nombre == "Cómo termina"


def test_siguen_el_orden_de_los_actos():
    """Spec-580: el orden sigue a los actos; los que tienen acto no retroceden."""
    criteria = catalog.direction_criteria()
    assert [c.id for c in criteria] == [
        "meta",
        "inquietud",
        "en_juego",
        "vulnerabilidad",
        "transgresion",
        "historia_secreta",
        "descubrimiento",
        "reaccion",
        "final",
    ]
    actos = [c.acto for c in criteria if c.acto]
    assert actos == sorted(actos) and actos[-1] == 5
    assert {c.id: c.acto for c in criteria}["descubrimiento"] == 3


def test_sin_jerga_en_lo_que_se_ve():
    """Spec-580 §2.2: nombre y «para qué sirve» sin términos de oficio."""
    jerga = ("escaleta", "taller", "clímax", "anagnórisis", "peripecia", "nudo", "criterio")
    for c in _by_id("José").values():
        texto = (c.nombre + " " + c.por_que).lower()
        assert not [j for j in jerga if j in texto], c.id


def test_para_que_sirve_en_lenguaje_llano():
    c = _by_id("José")
    assert c["meta"].por_que.endswith("de lo que José quiere.")
    assert "José" in c["en_juego"].por_que
    assert "{" not in "".join(x.por_que + x.nombre for x in c.values())


def test_sin_protagonista_dice_el_protagonista():
    c = _by_id("")
    assert c["meta"].nombre == "Qué quiere el protagonista"
    assert c["vulnerabilidad"].nombre == "En qué se equivoca el protagonista"
    assert (
        "a el " not in c["vulnerabilidad"].por_que and "de el " not in c["historia_secreta"].por_que
    )


def test_dos_formas_de_contarlo():
    """Spec-780 D4: «Como a un amigo» (la anécdota de la Spec-640, la de siempre) y «Como si
    lo escribieras» (relato escrito, sin exagerar). Confesión y crónica se leen como estas."""
    t = {o.id: o for o in catalog.tellings()}
    assert list(t) == ["caso", "escrito"]
    assert (t["caso"].label, t["caso"].guia, t["caso"].antes) == (
        "Como a un amigo",
        "anecdota",
        ("confesion",),
    )
    assert (t["escrito"].label, t["escrito"].guia) == ("Como si lo escribieras", "escrito")
    assert "sin adornos" in t["escrito"].voice


@pytest.mark.parametrize(
    "guardado, se_lee",
    [
        ("caso", "caso"),
        ("confesion", "caso"),
        ("cronica", "escrito"),
        ("escrito", "escrito"),
        ("", "caso"),
        ("x", "caso"),
    ],
)
def test_un_id_viejo_se_lee_como_el_que_lo_reemplazo(guardado, se_lee):
    from types import SimpleNamespace

    story = SimpleNamespace(direction=SimpleNamespace(telling=guardado))
    assert catalog.telling_de(story).id == se_lee
