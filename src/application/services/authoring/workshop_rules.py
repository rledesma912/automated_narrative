"""Reglas determinísticas del taller (Spec-530 §3.3 y decisiones 11–13).

No llaman al LLM: combinan cada ronda del Consultor con lo que ya había, filtran
las preguntas que «ya no suman», resuelven «Decidí vos» y dicen por qué terminó.
"""

import re
import unicodedata
from dataclasses import dataclass

from src.application.services.authoring import catalog
from src.domain.models import CriterionStatus, Direction, WorkshopItem, WorkshopLevel

MAX_ROUNDS = 5
MAX_OPTIONS = 3
_SIMILAR = 0.6  # Jaccard de palabras largas: desde acá dos preguntas son «la misma»

OPEN = (CriterionStatus.FALTA, CriterionStatus.PARCIAL)


@dataclass(frozen=True)
class Evaluation:
    """Lo que dijo el Consultor de un criterio en esta ronda."""

    criterion: str
    status: CriterionStatus  # cumple | parcial | falta
    question: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Finish:
    kind: str  # abierto | cumple | sin_preguntas | no_suma | tope
    text: str
    open_questions: int


def initial_items(direction: Direction | None, existing: list[WorkshopItem]) -> list[WorkshopItem]:
    """Un ítem por criterio de la dirección; el final intencional ya viene resuelto."""
    by_id = {w.criterion: w for w in existing if w.level == WorkshopLevel.DIRECCION}
    items = []
    for c in catalog.direction_criteria():
        item = by_id.get(c.id) or WorkshopItem(criterion=c.id, round=1)
        if c.id == "final" and direction and direction.ending_intentional and direction.ending:
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
    """Lo que el Consultor evalúa: ni lo intencional ni lo que el autor ya respondió."""
    return [w for w in items if w.status != CriterionStatus.INTENCIONAL and not w.answer]


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


def finish(items: list[WorkshopItem], round_: int | None = None) -> Finish:
    """Por qué terminó (o no) el taller, siempre visible para el usuario.

    Se calcula solo con lo guardado: una pregunta es «nueva» si se hizo en la
    última ronda (`question_round`).
    """
    round_ = current_round(items) if round_ is None else round_
    pending = [w for w in items if w.status in OPEN]
    questions = [w for w in pending if w.question]
    n = len(questions)
    new_questions = sum(1 for w in questions if w.question_round == round_)
    if not pending:
        return Finish(
            "cumple",
            "Todos los criterios cumplen o están decididos a propósito. Podés armar la escaleta.",
            0,
        )
    if round_ >= MAX_ROUNDS and n == 0:
        return Finish(
            "tope",
            f"Llegaste al máximo de {MAX_ROUNDS} rondas. "
            "Podés responder lo pendiente o armar la escaleta.",
            0,
        )
    if n == 0:
        return Finish("sin_preguntas", "La IA no tiene más preguntas. Podés armar la escaleta.", 0)
    if new_questions == 0:
        plural = "queda 1 pregunta" if n == 1 else f"quedan {n} preguntas"
        return Finish(
            "no_suma",
            f"La IA no encontró preguntas nuevas: {plural} sin responder de antes. "
            "Respondé lo que quieras o armá la escaleta.",
            n,
        )
    plural = "pregunta abierta" if n == 1 else "preguntas abiertas"
    text = (
        f"Queda{'' if n == 1 else 'n'} {n} {plural}. Podés responder, analizar de nuevo "
        "o pasar a la escaleta cuando quieras."
    )
    if round_ >= MAX_ROUNDS:
        text += f" (Es la última ronda: el máximo es {MAX_ROUNDS}.)"
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
        raise ValueError(f"El criterio {item.criterion} no tiene opciones para elegir")
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
    if item.question and item.question not in item.asked:
        return [*item.asked, item.question]
    return list(item.asked)


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
