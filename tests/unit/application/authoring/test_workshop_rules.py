import pytest

from src.application.services.authoring import workshop_rules as wr
from src.domain.models import CriterionStatus as S
from src.domain.models import Direction, WorkshopItem

CRITERIA = ["meta", "en_juego", "vulnerabilidad", "historia_secreta", "final"]


def _items(**overrides) -> list[WorkshopItem]:
    return [overrides.get(c, WorkshopItem(criterion=c)) for c in CRITERIA]


def test_items_iniciales_con_final_intencional():
    items = wr.initial_items(Direction(ending="En paz.", ending_intentional=True), [])
    assert [i.criterion for i in items] == CRITERIA
    final = items[-1]
    assert (final.status, final.answer) == (S.INTENCIONAL, "En paz.")
    assert "final" not in {i.criterion for i in wr.to_evaluate(items)}


def test_lo_respondido_no_se_evalua():
    items = _items(meta=WorkshopItem(criterion="meta", status=S.CUMPLE, answer="Llegar."))
    assert "meta" not in {i.criterion for i in wr.to_evaluate(items)}


def test_ronda_con_pregunta_nueva_y_cumple():
    items, new = wr.merge_round(
        _items(),
        [
            wr.Evaluation("meta", S.FALTA, "¿Qué quiere José?", ("a", "a", "b", "c", "d")),
            wr.Evaluation("en_juego", S.CUMPLE, "ignorada", ("x",)),
        ],
        1,
    )
    meta, en_juego = items[0], items[1]
    assert (meta.status, meta.question, meta.options) == (
        S.FALTA,
        "¿Qué quiere José?",
        ["a", "b", "c"],
    )
    assert (en_juego.status, en_juego.question, en_juego.options) == (S.CUMPLE, "", [])
    assert new == 1


def test_la_pregunta_pendiente_no_se_reformula():
    pending = WorkshopItem(criterion="meta", status=S.FALTA, question="¿Qué quiere?", options=["a"])
    items, new = wr.merge_round(
        _items(meta=pending), [wr.Evaluation("meta", S.PARCIAL, "¿Y qué quiere José?", ("z",))], 2
    )
    assert (items[0].question, items[0].options, items[0].status, items[0].round) == (
        "¿Qué quiere?",
        ["a"],
        S.PARCIAL,
        2,
    )
    assert new == 0


def test_una_pregunta_ya_hecha_no_vuelve():
    asked = WorkshopItem(criterion="meta", asked=["¿Qué quiere José esa noche en la ruta?"])
    items, new = wr.merge_round(
        _items(meta=asked),
        [wr.Evaluation("meta", S.FALTA, "¿Qué quiere José esa noche en la ruta?", ("x",))],
        2,
    )
    assert (items[0].question, new) == ("", 0)


def _q(round_asked: int) -> WorkshopItem:
    return WorkshopItem(
        criterion="a", status=S.FALTA, question="q", round=round_asked, question_round=round_asked
    )


@pytest.mark.parametrize(
    ("items", "round_", "kind"),
    [
        ([WorkshopItem(criterion="a", status=S.CUMPLE)], 1, "cumple"),
        ([_q(1)], 1, "abierto"),
        ([_q(1)], 2, "no_suma"),  # la pregunta es de una ronda anterior
        ([WorkshopItem(criterion="a", status=S.FALTA)], 1, "sin_preguntas"),
        ([_q(5)], 5, "tope"),
        ([WorkshopItem(criterion="a", status=S.FALTA)], 5, "tope"),
    ],
)
def test_fin_del_taller(items, round_, kind):
    assert wr.finish(items, round_).kind == kind


def test_el_fin_se_recalcula_con_lo_guardado():
    items = [_q(2), WorkshopItem(criterion="b", status=S.CUMPLE, round=2)]
    assert wr.finish(items).kind == "abierto"
    items = [_q(1).model_copy(update={"round": 2}), WorkshopItem(criterion="b", round=2)]
    assert wr.finish(items).kind == "no_suma"


def test_responder_cierra_la_pregunta():
    item = WorkshopItem(criterion="meta", status=S.FALTA, question="¿Qué?", options=["a", "b"])
    done = wr.answer(item, "  Llegar a casa ")
    assert (done.status, done.answer, done.question, done.options, done.asked) == (
        S.CUMPLE,
        "Llegar a casa",
        "",
        [],
        ["¿Qué?"],
    )


def test_decidi_vos_elige_la_primera_opcion():
    item = WorkshopItem(criterion="meta", status=S.FALTA, question="¿Qué?", options=["a", "b"])
    assert wr.decide_for_me(item).answer == "a"
    with pytest.raises(ValueError):
        wr.decide_for_me(WorkshopItem(criterion="meta"))


def test_intencional():
    item = WorkshopItem(criterion="final", status=S.FALTA, question="¿Y el final?")
    done = wr.mark_intentional(item, "En paz")
    assert (done.status, done.answer, done.question) == (S.INTENCIONAL, "En paz", "")


def test_similar():
    assert wr.similar("¿Qué quiere José esta noche?", "Que quiere Jose esta noche")
    assert not wr.similar("¿Qué quiere José?", "¿Qué pierde si choca el micro?")
