"""Spec-550 H7: los criterios del taller dicen de quién hablan y para qué sirven."""

from src.application.services.authoring import catalog


def _by_id(protagonist: str) -> dict[str, catalog.Criterion]:
    return {c.id: c.for_story(protagonist) for c in catalog.direction_criteria()}


def test_nombres_con_el_protagonista():
    c = _by_id("José")
    assert c["meta"].nombre == "Qué busca José"
    assert c["en_juego"].nombre == "Qué arriesga José"
    assert c["vulnerabilidad"].nombre == "Qué expone a José"
    assert c["historia_secreta"].nombre == "La historia secreta"
    assert c["final"].nombre == "El final"


def test_para_que_sirve_en_lenguaje_llano():
    c = _by_id("José")
    assert c["meta"].por_que.startswith("Lo que José quiere conseguir en esta historia")
    assert "José" in c["en_juego"].por_que
    assert "{" not in "".join(x.por_que + x.nombre for x in c.values())


def test_sin_protagonista_dice_el_protagonista():
    c = _by_id("")
    assert c["meta"].nombre == "Qué busca el protagonista"
    assert c["vulnerabilidad"].nombre == "Qué expone al protagonista"
    assert (
        "a el " not in c["vulnerabilidad"].por_que and "de el " not in c["historia_secreta"].por_que
    )
