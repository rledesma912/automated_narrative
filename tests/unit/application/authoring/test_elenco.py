"""Spec-700 B: los personajes que nombró la autora se suman solos; el aviso queda para
los que inventó la IA."""

from src.application.services.authoring import elenco
from src.application.services.authoring import workshop_rules as wr
from src.application.services.authoring.verifier import rule_warnings
from src.domain.models import ActOutline, Entity, OutlineWarning, TypedRule


def _ximena(story):
    """Como «El trabajo de Yadira»: narra Ximena; la idea nombra a Gael y a Yadira."""
    items = wr.initial_items(story.direction, [])
    items = [
        wr.answer(w, "La tía de Yadira, Doña Aurelia, sabe hacer trabajos.")
        if w.criterion == "inquietud"
        else w
        for w in items
    ]
    return story.model_copy(
        update={
            "protagonista": "Ximena: atiende la tienda de abarrotes de su mamá",
            "narrator_config": {"storyteller_name": "Ximena"},
            "personajes_full": [{"id": "P1", "name": "Ximena", "role": ""}],
            "direction": story.direction.model_copy(
                update={
                    "premise": "Ximena empieza una relación con Gael, que dejó a Yadira. "
                    "Sus amigas le advierten que no se meta con ella."
                }
            ),
            "workshop": items,
        }
    )


def test_de_la_autora_por_la_idea_las_respuestas_y_quien_narra(story):
    story = _ximena(story)
    assert elenco.de_la_autora(story, "Gael")
    assert elenco.de_la_autora(story, "Yadira (la ex)")  # sin la aclaración
    assert elenco.de_la_autora(story, "Doña Aurelia")  # de una respuesta
    assert elenco.de_la_autora(story, "Mamá de Ximena")  # «su mamá», de quien narra
    assert elenco.de_la_autora(story, "Amigas de Ximena")
    assert not elenco.de_la_autora(story, "Perro de Ximena")  # lo puso la IA
    assert not elenco.de_la_autora(story, "Amigos de Ximena")
    assert not elenco.de_la_autora(story, "Mamá de Gael")  # «de» otro: no alcanza la palabra
    assert not elenco.de_la_autora(story, "Gaelito")  # palabra entera


def test_de_la_autora_por_una_regla(story):
    story = _ximena(story)
    story.typed_rules = [
        TypedRule(
            id="r1", story_id=story.id, content="El cura nunca entra a la casa", applies_to_beat=2
        )
    ]
    assert elenco.de_la_autora(story, "El cura")


def test_personajes_de_la_autora_en_orden_sin_repetir(story):
    story = _ximena(story)
    story.entities = [
        Entity(story_id=story.id, order_index=0, name="La Llorona", nature_id="fantasma")
    ]
    acts = [
        ActOutline(number=2, on_stage=["Ximena", "Yadira", "Perro de Ximena"]),
        ActOutline(number=1, on_stage=["Ximena", "Gael (su novio)", "La Llorona"]),
        ActOutline(number=3, on_stage=["gael", "Doña Aurelia"]),
    ]
    assert elenco.personajes_de_la_autora(story, acts) == ["Gael", "Yadira", "Doña Aurelia"]


def test_con_personajes_los_suma_sin_parentesco_y_con_id_libre(story):
    story = _ximena(story)
    story.personajes_full = [{"id": "P1", "name": "Ximena"}, {"id": "P3", "name": "Gael"}]
    out = elenco.con_personajes(story, ["Yadira"])
    assert out.personajes_full[-1] == {
        "id": "P4",
        "name": "Yadira",
        "role": "",
        "kind": "persona",
        "relation": "",
    }
    assert elenco.con_personajes(story, []) is story


def test_parecido_letra_por_letra():
    cast = ["Ximena", "Amigas de Ximena", "Mamá de Ximena"]
    assert elenco.parecido("Amigos de Ximena", cast) == "Amigas de Ximena"
    assert elenco.parecido("Perro de Ximena", cast) == ""
    assert elenco.parecido("amigas de ximena", cast) == ""  # el mismo no es «parecido»


def test_sin_aviso_resuelve_solo_el_de_ese_nombre():
    act = ActOutline(
        number=2,
        warnings=[
            OutlineWarning(text="a", key=elenco.clave("El Sereno (de noche)"), source="regla"),
            OutlineWarning(text="b", key="sin_cambio", source="regla"),
        ],
    )
    assert [w.key for w in elenco.sin_aviso(act, "el sereno").warnings] == ["sin_cambio"]


def test_el_aviso_trae_el_nombre_y_el_parecido(story):
    story = _ximena(story)
    story.personajes_full.append({"id": "P2", "name": "Amigas de Ximena"})
    outline = [
        ActOutline(number=1, on_stage=["Ximena", "Perro de Ximena (Toby)", "Amigos de Ximena"])
    ]

    warnings = {w.key: w for w in rule_warnings(story, outline)[1]}

    perro = warnings["elenco:perro de ximena"]
    assert (perro.subject, perro.similar) == ("Perro de Ximena", "")
    assert perro.text.startswith("La IA puso a «Perro de Ximena» en este acto")
    amigos = warnings["elenco:amigos de ximena"]
    assert (amigos.subject, amigos.similar) == ("Amigos de Ximena", "Amigas de Ximena")
    assert amigos.text.endswith("¿Es «Amigas de Ximena»?")


def test_con_personajes_los_propuestos_llevan_quien_es(story):
    """Spec-730: la IA los sumó con quién es; la Voz lo recibe como `role`."""
    out = elenco.con_personajes(story, ["Don Ramón"], {"Don Ramón": "el sereno de la terminal"})
    assert out.personajes_full[-1]["role"] == "el sereno de la terminal"
