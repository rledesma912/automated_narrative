"""Spec-690 S2: la IA saca el final de la idea (D1, D11–D13)."""

import pytest

from src.application.services.authoring import final_de_la_idea as fdi
from src.application.services.authoring import workshop_rules
from src.domain.models import CriterionStatus, WorkshopItem, WorkshopLevel
from tests.unit.application.authoring.conftest import ScriptedLLM

IDEA = (
    "José maneja el último micro de la noche. Ve por el espejo a una mujer que murió ahí. "
    "La busca por todo el micro y no está. Días después, en la terminal, le cuentan que "
    "ella murió en ese asiento. Desde entonces nunca más maneja de noche."
)
INICIO = "Días después, en la terminal, le cuentan que ella murió en ese asiento."


def _story(story, idea=IDEA, ending="", item=None):
    d = story.direction.model_copy(update={"premise": idea, "ending": ending})
    return story.model_copy(update={"direction": d, "workshop": [item] if item else []})


def _final(answer, status=CriterionStatus.INTENCIONAL, asked=()):
    return WorkshopItem(
        criterion="final",
        level=WorkshopLevel.DIRECCION,
        status=status,
        answer=answer,
        asked=list(asked),
        round=1,
    )


# ── El corte ─────────────────────────────────────────────────────────────────


def test_corta_desde_el_inicio_hasta_el_final_de_la_idea():
    assert fdi.cut(IDEA, INICIO) == (
        "Días después, en la terminal, le cuentan que ella murió en ese asiento. "
        "Desde entonces nunca más maneja de noche."
    )


@pytest.mark.parametrize(
    "inicio",
    [
        "«Días  después, en la terminal,\nle cuentan que ella murió en ese asiento.»",
        "días después, en la terminal, le cuentan",
    ],
)
def test_el_corte_tolera_espacios_comillas_y_mayusculas(inicio):
    assert fdi.cut(IDEA, inicio).startswith("Días después")


@pytest.mark.parametrize("inicio", ["", "Al final se casa con la mujer del espejo."])
def test_si_no_esta_en_la_idea_no_inventa(inicio):
    assert fdi.cut(IDEA, inicio) == ""


# ── Cuándo corre ─────────────────────────────────────────────────────────────


async def test_deja_el_final_resuelto_y_marcado(story):
    llm = ScriptedLLM({"cuenta_final": True, "inicio": INICIO})
    item = await fdi.FinalDeLaIdea(llm).ensure(_story(story))
    assert item.status == CriterionStatus.INTENCIONAL
    assert item.answer.startswith("Días después") and item.answer.endswith("de noche.")
    assert workshop_rules.DE_LA_IDEA in item.asked
    assert "LA IDEA:\n" + IDEA in llm.calls[0]["prompt"]


async def test_si_la_idea_no_cuenta_el_final_no_guarda_nada(story):
    llm = ScriptedLLM({"cuenta_final": False, "inicio": ""})
    assert await fdi.FinalDeLaIdea(llm).ensure(_story(story)) is None


@pytest.mark.parametrize(
    "kw",
    [
        {"ending": "Descansa en paz."},  # el «¿Cómo termina?» viejo
        {"item": _final("Se va del pueblo.", CriterionStatus.CUMPLE)},  # lo escribió en «Preguntas»
        {"item": _final("", CriterionStatus.FALTA, [workshop_rules.FINAL_PREGUNTAR])},  # D13
        {
            "item": _final(
                "Desde entonces nunca más maneja de noche.", asked=[workshop_rules.DE_LA_IDEA]
            )
        },
        {"idea": ""},
    ],
)
async def test_no_llama_a_la_ia_si_no_hace_falta(story, kw):
    llm = ScriptedLLM()  # sin respuestas: una llamada fallaría
    assert await fdi.FinalDeLaIdea(llm).ensure(_story(story, **kw)) is None
    assert llm.calls == []


async def test_si_la_idea_cambio_se_vuelve_a_sacar(story):
    """D12: el final sacado ya no está en la idea."""
    viejo = _final("Se muda a otra ciudad.", asked=[workshop_rules.DE_LA_IDEA])
    llm = ScriptedLLM({"cuenta_final": True, "inicio": INICIO})
    item = await fdi.FinalDeLaIdea(llm).ensure(_story(story, item=viejo))
    assert item.answer.startswith("Días después")
    assert item.asked.count(workshop_rules.DE_LA_IDEA) == 1


async def test_si_la_idea_cambio_y_ya_no_cuenta_el_final_vuelve_a_preguntarse(story):
    viejo = _final("Se muda a otra ciudad.", asked=[workshop_rules.DE_LA_IDEA])
    llm = ScriptedLLM({"cuenta_final": False, "inicio": ""})
    item = await fdi.FinalDeLaIdea(llm).ensure(_story(story, item=viejo))
    assert (item.status, item.answer, item.asked) == (CriterionStatus.FALTA, "", [])


# ── Lo que hace la autora (D11, D13) ─────────────────────────────────────────


def test_cambiarlo_lo_hace_suyo():
    item = workshop_rules.answer(
        _final("Días después…", asked=[workshop_rules.DE_LA_IDEA]), "Se va."
    )
    assert workshop_rules.DE_LA_IDEA not in item.asked


def test_que_la_ia_lo_vuelva_a_preguntar_deja_de_sacarlo_de_la_idea():
    item = workshop_rules.reopen(_final("Días después…", asked=[workshop_rules.DE_LA_IDEA]))
    assert item.status == CriterionStatus.FALTA
    assert workshop_rules.FINAL_PREGUNTAR in item.asked
    assert workshop_rules.DE_LA_IDEA not in item.asked


def test_reabrir_otro_criterio_no_marca_el_final():
    otro = WorkshopItem(criterion="meta", level=WorkshopLevel.DIRECCION, answer="x", round=1)
    assert workshop_rules.FINAL_PREGUNTAR not in workshop_rules.reopen(otro).asked
