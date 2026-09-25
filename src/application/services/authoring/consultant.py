"""Consultor del taller (Spec-530 §5.1): evalúa la historia y pregunta por los huecos."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, create_model

from src.application.services.authoring import catalog, context, workshop_rules
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import CriterionStatus, Story, WorkshopItem

ROLE = "consultor"


@dataclass(frozen=True)
class WorkshopRound:
    items: list[WorkshopItem]
    finish: workshop_rules.Finish
    elapsed_s: float


class WorkshopConsultant:
    def __init__(self, llm: LLMProvider, templates: TemplateLoader | None = None):
        self.llm = llm
        self.templates = templates or TemplateLoader()

    async def analyze(self, story: Story) -> WorkshopRound:
        """Una ronda del taller: evalúa lo pendiente y devuelve el taller actualizado."""
        items = workshop_rules.initial_items(story.direction, story.workshop)
        round_ = max((w.round for w in story.workshop), default=0) + 1
        pending = workshop_rules.to_evaluate(items)
        if not pending:
            return WorkshopRound(items, workshop_rules.finish(items, round_), 0.0)

        story_view = story.model_copy(update={"workshop": items})
        output = _output_model([w.criterion for w in pending])
        result, elapsed = await generate_structured(
            self.llm,
            role=ROLE,
            prompt=self._prompt(story_view, pending),
            system_prompt=self.templates.load("authoring_consultant_system.md"),
            output=output,
        )
        evaluations = [
            workshop_rules.Evaluation(
                criterion=e.criterio,
                status=CriterionStatus(e.estado),
                question=e.pregunta,
                options=tuple(e.opciones),
            )
            for e in result.evaluaciones
        ]
        merged, new_questions = workshop_rules.merge_round(items, evaluations, round_)
        return WorkshopRound(merged, workshop_rules.finish(merged, round_, new_questions), elapsed)

    def _prompt(self, story: Story, pending: list[WorkshopItem]) -> str:
        criterios = "\n".join(
            f"- {c.id}: {c.pregunta}"
            for c in (catalog.criterion(w.criterion) for w in pending)
            if c
        )
        return self.templates.load("authoring_consultant.md").format(
            objetivo=context.OBJETIVO,
            historia=context.story_block(story),
            decisiones=context.decisions_block(story),
            pendientes=context.pending_block(story),
            criterios=criterios,
        )


def _output_model(criteria: list[str]) -> type[BaseModel]:
    """Esquema de la ronda: solo los criterios pendientes (el modelo no puede inventar otros)."""
    evaluation = create_model(
        "EvaluacionCriterio",
        criterio=(Literal[tuple(criteria)], ...),
        estado=(Literal["cumple", "parcial", "falta"], ...),
        pregunta=(str, ...),
        opciones=(list[str], ...),
    )
    return create_model("RondaTaller", evaluaciones=(list[evaluation], ...))
