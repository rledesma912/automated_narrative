"""Spec-700 A3/A4: con la idea cambiada, la IA se fija qué respuestas ya no coinciden.

Corre en el job `consult`, antes del Consultor, solo si la idea cambió desde la última
ronda (D17). Señala sin pisar: la respuesta queda como está, con la marca
`·no_coincide:<motivo>` (D18), hasta que la autora la cambie o diga «Está bien así».
"""

from typing import Literal

from pydantic import BaseModel, create_model

from src.application.services.authoring import catalog, context, molde, workshop_rules
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import CriterionStatus, Story, WorkshopItem, WorkshopLevel

ROLE = "consultor"


def a_revisar(story: Story) -> list[WorkshopItem]:
    """D19: las respuestas del molde (`cumple` con texto) y el final decidido que no salió
    de la idea (el viejo o un «Cambiar»: el que salió de la idea lo vuelve a sacar la 690).
    Lo demás que está «a propósito» es decisión de la autora y no se revisa."""
    ids = set(molde.for_story(story).ids)
    out = []
    for w in story.workshop:
        if w.level != WorkshopLevel.DIRECCION or w.criterion not in ids or not w.answer.strip():
            continue
        final = (
            w.criterion == "final"
            and w.status == CriterionStatus.INTENCIONAL
            and workshop_rules.DE_LA_IDEA not in w.asked
        )
        if w.status == CriterionStatus.CUMPLE or final:
            out.append(w)
    return out


class RevisorDeRespuestas:
    def __init__(self, llm: LLMProvider, templates: TemplateLoader | None = None):
        self.llm = llm
        self.templates = templates or TemplateLoader()

    def prompt(self, story: Story, items: list[WorkshopItem]) -> str:
        t = self.templates.fragment
        protagonist = context.protagonist(story)
        rows = []
        for w in items:
            c = catalog.criterion(w.criterion)
            nombre = c.for_story(protagonist).nombre if c else w.criterion
            asked = workshop_rules.questions(w)
            rows.append(
                t(
                    "asistente/decisiones/con_pregunta",
                    id=w.criterion,
                    nombre=nombre,
                    pregunta=asked[-1],
                    texto=w.answer,
                )
                if asked
                else t(
                    "asistente/decisiones/respondida", id=w.criterion, nombre=nombre, texto=w.answer
                )
            )
        d = story.direction
        idea = (d.premise if d and d.premise else story.sinopsis).strip()
        return self.templates.load("authoring_revisor.md").format(
            idea=idea, respuestas="\n".join(rows)
        )

    async def revisar(self, story: Story) -> list[WorkshopItem]:
        """Los ítems que cambian (marcados, o desmarcados si ahora coinciden)."""
        items = a_revisar(story)
        if not items:
            return []
        result, _ = await generate_structured(
            self.llm,
            role=ROLE,
            prompt=self.prompt(story, items),
            system_prompt=self.templates.load("authoring_revisor_system.md"),
            output=_output_model([w.criterion for w in items]),
        )
        by_id = {w.criterion: w for w in items}
        out = []
        for r in result.revisiones:
            item = by_id.pop(r.criterio, None)
            if item is None:
                continue
            motivo = " ".join(r.motivo.split())
            updated = (
                workshop_rules.mark_no_coincide(item, motivo)
                if not r.coincide and motivo
                else workshop_rules.keep(item)
            )
            if updated != item:
                out.append(updated)
        return out


def apply(story: Story, items: list[WorkshopItem]) -> Story:
    """La historia con esos ítems reemplazados (para seguir sin releer la base)."""
    by_key = {(w.level, w.criterion): w for w in items}
    workshop = [by_key.pop((w.level, w.criterion), w) for w in story.workshop]
    return story.model_copy(update={"workshop": workshop})


def _output_model(criteria: list[str]) -> type[BaseModel]:
    revision = create_model(
        "RevisionRespuesta",
        criterio=(Literal[tuple(criteria)], ...),
        coincide=(bool, ...),
        motivo=(str, ...),
    )
    return create_model("RevisionDeRespuestas", revisiones=(list[revision], ...))
