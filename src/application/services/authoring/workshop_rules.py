"""Reglas determinísticas del taller (Spec-530 §3.3 y decisiones 11–13).

No llaman al LLM: combinan cada ronda del Consultor con lo que ya había, filtran
las preguntas que «ya no suman», resuelven «Decidí vos» y dicen por qué terminó.
"""

import re
import unicodedata
from dataclasses import dataclass

from src.application.services.authoring import catalog
from src.domain.models import CriterionStatus, Direction, WorkshopItem, WorkshopLevel
from src.messages import message

MAX_ROUNDS = 5
MAX_OPTIONS = 3
_SIMILAR = 0.6  # Jaccard de palabras largas: desde acá dos preguntas son «la misma»

OPEN = (CriterionStatus.FALTA, CriterionStatus.PARCIAL)
# Spec-670 D12: el autor reabrió un «No va en tu historia»: en ese criterio la IA ya no
# puede volver a decir que no va (si no, reabrir sería un ida y vuelta sin fin).
NO_APLICA_RECHAZADO = "·no_aplica_rechazado"
# Spec-690: el final que se sacó de la idea (D11) y el que la autora pidió que se lo
# pregunten (D13: ya no se saca de la idea ni del «¿Cómo termina?» viejo).
DE_LA_IDEA = "·de_la_idea"
FINAL_PREGUNTAR = "·final_preguntar"
MAL_ELEGIDA = 2  # D8: desde cuántos criterios de la forma que no van se avisa


@dataclass(frozen=True)
class Evaluation:
    """Lo que dijo el Consultor de un criterio en esta ronda."""

    criterion: str
    status: CriterionStatus  # cumple | parcial | falta
    question: str = ""
    options: tuple[str, ...] = ()
    reason: str = ""  # Spec-670 D8: por qué no va (con `no_aplica`)


@dataclass(frozen=True)
class Finish:
    kind: str  # abierto | cumple | sin_preguntas | no_suma | tope | respondido | mal_elegida
    text: str
    open_questions: int


def initial_items(
    direction: Direction | None,
    existing: list[WorkshopItem],
    criteria: tuple[catalog.Criterion, ...] | None = None,
) -> list[WorkshopItem]:
    """Un ítem por criterio del molde (Spec-670: `criteria`; sin eso, el de siempre); el
    final intencional ya viene resuelto. Los guardados de otros criterios no entran (D11)."""
    by_id = {w.criterion: w for w in existing if w.level == WorkshopLevel.DIRECCION}
    items = []
    for c in criteria if criteria is not None else catalog.direction_criteria():
        item = by_id.get(c.id) or WorkshopItem(criterion=c.id, round=1)
        # Spec-690 D14: el final viejo de «Tu idea» entra solo si «Preguntas» no tiene uno
        # (antes lo pisaba en cada ronda, aunque la autora lo hubiera cambiado ahí).
        if (
            c.id == "final"
            and direction
            and direction.ending
            and not item.answer.strip()
            and FINAL_PREGUNTAR not in item.asked
        ):
            item = item.model_copy(
                update={
                    "status": CriterionStatus.INTENCIONAL,
                    "answer": direction.ending,
                    "question": "",
                    "options": [],
                }
            )
        items.append(item)
    return items


def to_evaluate(items: list[WorkshopItem]) -> list[WorkshopItem]:
    """Lo que el Consultor evalúa: ni lo intencional, ni lo que no va en la historia
    (Spec-670 D8), ni lo que el autor ya respondió."""
    done = (CriterionStatus.INTENCIONAL, CriterionStatus.NO_APLICA)
    return [w for w in items if w.status not in done and not w.answer]


def questions(item: WorkshopItem) -> list[str]:
    """Las preguntas que ya se hicieron, sin las marcas (`·…`) que viajan en `asked`."""
    return [a for a in item.asked if not a.startswith("·")]


def no_aplica_rejected(item: WorkshopItem) -> bool:
    """D12: el autor pidió que se lo pregunten igual."""
    return NO_APLICA_RECHAZADO in item.asked


def reopen(item: WorkshopItem) -> WorkshopItem:
    """Vuelve a evaluarse en la próxima ronda. Si era «No va en tu historia», queda la
    marca para que la IA no lo vuelva a descartar (D12)."""
    asked = [a for a in item.asked if a != DE_LA_IDEA]
    if item.status == CriterionStatus.NO_APLICA and NO_APLICA_RECHAZADO not in asked:
        asked.append(NO_APLICA_RECHAZADO)
    if item.criterion == "final" and FINAL_PREGUNTAR not in asked:
        asked.append(FINAL_PREGUNTAR)  # Spec-690 D13: ya no se saca de la idea
    question = "" if item.status == CriterionStatus.NO_APLICA else item.question
    return item.model_copy(
        update={"status": CriterionStatus.FALTA, "answer": "", "question": question, "asked": asked}
    )


def merge_round(
    items: list[WorkshopItem], evaluations: list[Evaluation], round_: int
) -> tuple[list[WorkshopItem], int]:
    """Aplica una ronda. Devuelve los ítems nuevos y cuántas preguntas nuevas trajo.

    Una pregunta que el autor no respondió se mantiene tal cual: el Consultor tiende a
    reformularla en cada ronda y eso no suma. Solo se actualiza su semáforo.
    """
    by_id = {e.criterion: e for e in evaluations}
    evaluable = {w.criterion for w in to_evaluate(items)}
    new_questions = 0
    out = []
    for item in items:
        ev = by_id.get(item.criterion)
        if ev is None or item.criterion not in evaluable:
            out.append(item)
            continue
        asked = list(item.asked)
        if item.question and ev.status in OPEN:
            # Pendiente de una ronda anterior: misma pregunta, semáforo al día.
            out.append(item.model_copy(update={"status": ev.status, "round": round_}))
            continue
        if item.question and item.question not in asked:
            asked.append(item.question)
        if ev.status == CriterionStatus.NO_APLICA and not no_aplica_rejected(item):
            # D8 / D12: no se pregunta; el motivo queda en `question` para mostrarlo.
            out.append(
                item.model_copy(
                    update={
                        "status": CriterionStatus.NO_APLICA,
                        "question": " ".join(ev.reason.split()),
                        "options": [],
                        "round": round_,
                        "question_round": 0,
                        "asked": asked,
                    }
                )
            )
            continue
        if ev.status == CriterionStatus.NO_APLICA:
            ev = Evaluation(ev.criterion, CriterionStatus.FALTA, ev.question, ev.options)
        if ev.status == CriterionStatus.CUMPLE:
            out.append(
                item.model_copy(
                    update={
                        "status": CriterionStatus.CUMPLE,
                        "question": "",
                        "options": [],
                        "round": round_,
                        "asked": asked,
                    }
                )
            )
            continue
        question = ev.question.strip()
        if question and any(similar(question, q) for q in asked):
            question = ""  # ya se preguntó antes: no suma
        if question:
            new_questions += 1
        options = clean_options(ev.options) if question else []
        question_round = round_ if question else 0
        out.append(
            item.model_copy(
                update={
                    "status": ev.status,
                    "question": question,
                    "options": options,
                    "round": round_,
                    "question_round": question_round,
                    "asked": asked,
                }
            )
        )
    return out, new_questions


def current_round(items: list[WorkshopItem]) -> int:
    return max((w.round for w in items), default=0)


def finish(
    items: list[WorkshopItem], round_: int | None = None, form_criteria: tuple[str, ...] = ()
) -> Finish:
    """Por qué terminó (o no) el taller, siempre visible para el usuario.

    Se calcula solo con lo guardado: una pregunta es «nueva» si se hizo en la
    última ronda (`question_round`). Spec-670 D8: si varios criterios de la forma
    (`form_criteria`) no van en la historia, la forma está mal elegida y eso se dice primero.
    """
    round_ = current_round(items) if round_ is None else round_
    no_van = [
        w for w in items if w.criterion in form_criteria and w.status == CriterionStatus.NO_APLICA
    ]
    if len(no_van) >= MAL_ELEGIDA:
        return Finish("mal_elegida", message("workshop.mal_elegida", n=len(no_van)), 0)
    pending = [w for w in items if w.status in OPEN]
    questions = [w for w in pending if w.question]
    n = len(questions)
    new_questions = sum(1 for w in questions if w.question_round == round_)
    if items and not to_evaluate(items):
        # Todo respondido o decidido por el autor: la IA no tiene nada que mirar y
        # «Preguntame lo que falta» no haría nada (la pantalla lo esconde).
        return Finish("respondido", message("workshop.respondido"), 0)
    if not pending:
        return Finish("cumple", message("workshop.cumple"), 0)
    if round_ >= MAX_ROUNDS and n == 0:
        return Finish("tope", message("workshop.tope", maximo=MAX_ROUNDS), 0)
    if n == 0:
        return Finish("sin_preguntas", message("workshop.sin_preguntas"), 0)
    if new_questions == 0:
        left = message("workshop.queda_una") if n == 1 else message("workshop.quedan", n=n)
        return Finish("no_suma", message("workshop.no_suma", quedan=left), n)
    text = message("workshop.abierto_una") if n == 1 else message("workshop.abierto", n=n)
    if round_ >= MAX_ROUNDS:
        text += message("workshop.ultima_vuelta", maximo=MAX_ROUNDS)
        return Finish("tope", text, n)
    return Finish("abierto", text, n)


def answer(item: WorkshopItem, text: str) -> WorkshopItem:
    """El autor respondió (una opción o con sus palabras): la pregunta queda cerrada."""
    return item.model_copy(
        update={
            "status": CriterionStatus.CUMPLE,
            "answer": text.strip(),
            "question": "",
            "options": [],
            "question_round": 0,
            "asked": _with_question(item),
        }
    )


def decide_for_me(item: WorkshopItem) -> WorkshopItem:
    """«Decidí vos» (decisión 13): la primera opción, la que la IA propone como más fuerte."""
    if not item.options:
        raise ValueError(message("workshop.sin_opciones", criterio=item.criterion))
    return answer(item, item.options[0])


def mark_intentional(item: WorkshopItem, text: str = "") -> WorkshopItem:
    """«Es así a propósito»: queda como está y no se vuelve a preguntar."""
    return item.model_copy(
        update={
            "status": CriterionStatus.INTENCIONAL,
            "answer": text.strip() or item.answer,
            "question": "",
            "options": [],
            "question_round": 0,
            "asked": _with_question(item),
        }
    )


def _with_question(item: WorkshopItem) -> list[str]:
    """`asked` con la pregunta actual. Spec-690: si la autora lo toca, deja de ser «sacado
    de la idea» (es suyo y no se vuelve a sacar)."""
    asked = [a for a in item.asked if a != DE_LA_IDEA]
    if item.question and item.question not in asked:
        return [*asked, item.question]
    return asked


def clean_options(options) -> list[str]:
    seen, out = set(), []
    for o in options:
        o = " ".join(str(o).split())
        key = normalize(o)
        if o and key not in seen:
            seen.add(key)
            out.append(o)
    return out[:MAX_OPTIONS]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9ñ ]+", " ", t).strip()


def similar(a: str, b: str) -> bool:
    wa = {w for w in normalize(a).split() if len(w) > 3}
    wb = {w for w in normalize(b).split() if len(w) > 3}
    if not wa or not wb:
        return normalize(a) == normalize(b)
    return len(wa & wb) / len(wa | wb) >= _SIMILAR
