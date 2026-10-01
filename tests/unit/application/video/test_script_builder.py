"""Spec-610 T2.3: chequeos y armado del paquete, sin LLM."""

import uuid

import pytest

from src.application.services import narrative_acts
from src.application.services.video.config import video_config
from src.application.services.video.schema import BloqueIA, MomentoIA, PaqueteIA
from src.application.services.video.script_builder import VideoScriptBuilder, find_phrase

CONTENT = (
    "## Acto 1\n\nNunca se lo conté a nadie, ni a mi mujer.\n\nEsa noche venía manejando.\n\n"
    "## Acto 2\n\nBajé a mirar el motor.\n\nHabía siluetas entre los troncos.\n\nSubí al camión."
)
ACTS = narrative_acts.split(CONTENT)
INTRO = " ".join(["Bienvenidos a mi cripta, pónganse cómodos."] * 10)  # 60 palabras
OUTRO = " ".join(["Conozco a algunos de ustedes, no me quedaría."] * 15) + " Buenas noches."


def _builder() -> VideoScriptBuilder:
    return VideoScriptBuilder(video_config())


def _bloques() -> list[BloqueIA]:
    return [
        BloqueIA(
            acto=1, desde=1, hasta=2, indicacion="Tranquilo.", enfasis=["Nunca"], pausa="larga"
        ),
        BloqueIA(acto=2, desde=1, hasta=1, indicacion="Seco.", enfasis=[], pausa="corta"),
        BloqueIA(
            acto=2, desde=2, hasta=3, indicacion="Lento.", enfasis=["siluetas"], pausa="larga"
        ),
    ]


def _momento(acto, desde, hasta, **cambios) -> MomentoIA:
    datos = dict(
        acto=acto,
        desde=desde,
        hasta=hasta,
        fuerte=False,
        que_se_ve="La ruta",
        lugar="ruta",
        prompt_imagen="An empty road at night, no people, 16:9",
        prompt_movimiento="Slow push-in.",
        transicion="corte",
        sonido="Viento",
    )
    datos.update(cambios)
    return MomentoIA(**datos)


def _momentos() -> list[MomentoIA]:
    return [
        _momento(1, 1, 1),
        _momento(1, 2, 2),
        _momento(2, 1, 1, fuerte=True),
        _momento(2, 2, 2),
        _momento(2, 3, 3),
    ]


def _paquete(**cambios) -> PaqueteIA:
    datos = dict(narra="hombre", bloques=_bloques(), momentos=_momentos(), intro=INTRO, outro=OUTRO)
    datos.update(cambios)
    return PaqueteIA(**datos)


def test_un_paquete_bueno_no_tiene_problemas():
    assert _builder().check(_paquete(), ACTS) == []


def test_bloques_que_no_cubren_un_acto():
    bloques = _bloques()[:2]  # falta el bloque de los párrafos 2-3 del acto 2
    problems = _builder().check(_paquete(bloques=bloques), ACTS)
    assert problems == [
        "Los bloques no cubren el acto 2 entero, en orden y sin repetir: faltan los párrafos 2, 3."
    ]


def test_momentos_que_se_pisan_o_se_pasan():
    momentos = _momentos() + [_momento(2, 3, 4)]
    problems = _builder().check(_paquete(momentos=momentos), ACTS)
    assert any("se repiten o se pisan los párrafos 3" in p for p in problems)
    assert any("el párrafo 4 no existe (el acto tiene 3)" in p for p in problems)


def test_un_acto_que_no_existe():
    bloques = _bloques() + [
        BloqueIA(acto=9, desde=1, hasta=1, indicacion="", enfasis=[], pausa="corta")
    ]
    problems = _builder().check(_paquete(bloques=bloques), ACTS)
    assert "Hay un bloque o un momento en el acto 9, que el relato no tiene." in problems


def test_un_enfasis_que_no_esta_en_el_bloque():
    bloques = _bloques()
    bloques[1] = bloques[1].model_copy(update={"enfasis": ["siluetas"]})  # está en otro bloque
    problems = _builder().check(_paquete(bloques=bloques), ACTS)
    assert problems == ["En el bloque 2 (acto 2), «siluetas» no está tal cual en el texto."]


def test_pocos_momentos_para_un_relato_largo():
    largo = narrative_acts.split(
        "## Acto 1\n\n" + "\n\n".join(f"Párrafo {n}." for n in range(1, 21))
    )
    paquete = _paquete(
        bloques=[BloqueIA(acto=1, desde=1, hasta=20, indicacion="", enfasis=[], pausa="larga")],
        momentos=[_momento(1, 1, 20)],
    )
    assert "Hay 1 momentos: tienen que ser entre 10 y 15." in _builder().check(paquete, largo)


def test_prompt_con_una_persona_pero_no_las_negadas():
    momentos = _momentos()
    momentos[3] = momentos[3].model_copy(
        update={"prompt_imagen": "A dark forest with a man standing, no creatures, without faces"}
    )
    problems = _builder().check(_paquete(momentos=momentos), ACTS)
    assert problems == [
        "El momento 4 usa «man» en un prompt: en pantalla no hay personas ni la amenaza."
    ]


def test_outro_sin_buenas_noches_y_largos():
    problems = _builder().check(_paquete(intro="Hola.", outro=OUTRO + " Chau."), ACTS)
    assert "El outro tiene que terminar con «Buenas noches»." in problems
    assert "La intro tiene 1 palabras: tiene que tener entre 50 y 80." in problems


@pytest.mark.parametrize("final", ["Buenas noches.", "Buenas noches", "Buenas noches…"])
def test_el_cierre_admite_la_puntuacion(final):
    outro = OUTRO.removesuffix("Buenas noches.") + final
    assert _builder().check(_paquete(outro=outro), ACTS) == []


def test_armar_el_paquete():
    narrative_id = uuid.uuid4()
    script = _builder().build(_paquete(), ACTS, narrative_id, CONTENT)

    assert script.lector == "Lucas"
    assert script.parrafos_por_acto == {1: 2, 2: 3}
    assert script.bloques[0].marcas[0].model_dump() == {
        "desde_palabra": 0,
        "hasta_palabra": 0,
        "texto": "Nunca",
    }
    # «siluetas» es la palabra 1 del bloque (párrafos 2-3 del acto 2).
    assert script.bloques[2].marcas[0].desde_palabra == 1
    assert script.momentos[0].transicion == "Corte"  # de la lista, aunque vino en minúscula
    assert script.momentos[2].tipo == "video"  # el momento fuerte
    assert len(script.narrative_hash) == 16
    assert _builder().build(_paquete(), ACTS, narrative_id, CONTENT).seed == script.seed


def test_find_phrase_ignora_mayusculas_y_signos_y_no_pisa():
    tokens = "¿Quién anda ahí? Nadie. ¿Quién anda?".split()
    assert find_phrase(tokens, "quién anda", set()) == (0, 1)
    assert find_phrase(tokens, "quién anda", {0, 1}) == (4, 5)
    assert find_phrase(tokens, "nadie", set()) == (3, 3)
    assert find_phrase(tokens, "alguien", set()) is None
