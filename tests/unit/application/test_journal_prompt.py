"""Tests de regresión para build_journal_prompt() — Spec-060 Issue 1.

El template journal.md usa {{ }} como escape de Python .format(). Estos tests
verifican que el output contiene { } simples (JSON válido), no {{ }} literales.
Si alguien "corrige" el template quitando los {{ se producirá KeyError — este
test lo detecta.
"""

from src.application.services import PromptBuilder
from src.domain.models import Beat, NarrativeJournal, Story


def _story() -> Story:
    return Story(
        title="La Casa",
        protagonista="Elena",
        relator="primera_persona",
        sinopsis="Una mujer entra a una casa abandonada.",
        atmosfera="terror",
    )


def _beat() -> Beat:
    return Beat(
        number=1,
        summary="Elena escucha pasos en el piso de arriba.",
        content="El crujido del piso me heló la sangre.",
        status="completed",
    )


class TestJournalPromptBraces:
    def test_prompt_no_contiene_doble_llave_apertura(self):
        builder = PromptBuilder()
        prompt = builder.build_journal_prompt(_story(), _beat())
        assert "{{" not in prompt

    def test_prompt_no_contiene_doble_llave_cierre(self):
        builder = PromptBuilder()
        prompt = builder.build_journal_prompt(_story(), _beat())
        assert "}}" not in prompt

    def test_prompt_contiene_llave_apertura_simple(self):
        """El bloque JSON tiene { simple — el LLM recibe JSON bien formado."""
        builder = PromptBuilder()
        prompt = builder.build_journal_prompt(_story(), _beat())
        assert "{\n" in prompt or "{ " in prompt or '{\n  "' in prompt

    def test_prompt_con_journal_previo_no_contiene_dobles_llaves(self):
        journal = NarrativeJournal(
            last_events="Elena subió las escaleras.",
            unresolved_mysteries="¿Quién hace los ruidos?",
            physical_emotional_state="Asustada, en el rellano.",
        )
        builder = PromptBuilder()
        prompt = builder.build_journal_prompt(_story(), _beat(), previous_journal=journal)
        assert "{{" not in prompt
        assert "}}" not in prompt

    def test_prompt_contiene_campos_de_historia(self):
        builder = PromptBuilder()
        prompt = builder.build_journal_prompt(_story(), _beat())
        assert "La Casa" in prompt
        assert "Elena" in prompt

    def test_prompt_contiene_contenido_del_beat(self):
        builder = PromptBuilder()
        prompt = builder.build_journal_prompt(_story(), _beat())
        assert "Elena escucha pasos" in prompt
