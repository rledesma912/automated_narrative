"""Spec-780 D4: «Como si lo escribieras» cambia el bloque de la guía de oficio de la Voz;
«Como a un amigo» (y «confesión», de las historias viejas) le deja lo de siempre."""

import pytest

from src.application.services.authoring.outline_narrator import OutlineNarrator
from tests.unit.application.authoring.test_voice_prompts_snapshot import _memory, _story


def _system(telling: str) -> str:
    story = _story()
    story = story.model_copy(
        update={"direction": story.direction.model_copy(update={"telling": telling})}
    )
    act = story.outline[0]
    return OutlineNarrator(llm=None).voice_prompts(story, act, _memory(1), "")[0]


def test_como_si_lo_escribieras_pide_un_relato_escrito():
    system = _system("escrito")
    assert "CONTALO COMO UN RELATO ESCRITO:" in system
    assert "- Escribí con oraciones completas, cada una con su verbo" in system
    assert "Sin exagerar: el miedo lo da lo que pasa" in system
    assert "Contalo como un relato escrito: cuidá cada oración" in system
    # No le quedan las indicaciones de la anécdota.
    assert "ANÉCDOTA" not in system and "sobremesa, no un cuento escrito" not in system
    assert "Contalo como alguien que se lo cuenta a otra persona" not in system


@pytest.mark.parametrize("telling", ["caso", "confesion", ""])
def test_como_a_un_amigo_es_la_anecdota_de_siempre(telling):
    system = _system(telling)
    assert "CONTALO COMO UNA ANÉCDOTA:" in system
    assert "- Contalo como alguien que se lo cuenta a otra persona: oraciones completas" in system
    assert "RELATO ESCRITO" not in system
    # Confesión y sin elegir se leen como «Como a un amigo» (su línea de estilo).
    assert "Contalo como un caso que le contás a unos amigos" in system
