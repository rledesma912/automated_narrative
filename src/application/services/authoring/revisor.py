"""Spec-700 A3/A4: con la idea cambiada, la IA se fija qué respuestas ya no coinciden.

Corre en el job `consult`, antes del Consultor, solo si la idea cambió desde la última
ronda (D17). Señala sin pisar: la respuesta queda como está, con la marca
`·no_coincide:<motivo>` (D18), hasta que la autora la cambie o diga «Está bien así».

S4 (D25, D26): corre en Claude, con su propio rol. Un perfil sin `revisor`, o una
llamada que falla, deja en cambio la marca `idea_sin_revisar` («Preguntas» muestra qué
cambió, sin IA).
"""

from typing import Literal

from pydantic import BaseModel, create_model

from src.application.services.authoring import catalog, context, molde, workshop_rules
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.template_loader import TemplateLoader
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.models import CriterionStatus, Story, WorkshopItem, WorkshopLevel

ROLE = "revisor"


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


def con_ia() -> bool:
    """D25: solo los perfiles que declaran el rol revisan con IA (con gemma no servía)."""
    return settings.has_role(ROLE)


def sin_revisar(story: Story) -> Story:
    """D26: la historia con la idea de antes guardada para mostrar qué cambió (la más vieja
    si ya había una). Sin respuestas que revisar no hace falta la nota."""
    d = story.direction
    if d is None or d.idea_sin_revisar or not a_revisar(story):
        return story
    return story.model_copy(
        update={"direction": d.model_copy(update={"idea_sin_revisar": d.idea_preguntas})}
    )


def pendiente(story: Story) -> dict | None:
    """D27: qué cambió desde la idea que no se pudo revisar, oración por oración (o nada,
    si no hay marca o la idea volvió a ser la de antes)."""
    d = story.direction
    if d is None or not d.idea_sin_revisar:
        return None
    sacado, agregado = context.lo_que_cambio(d.idea_sin_revisar, context.idea(story))
    return {"sacado": sacado, "agregado": agregado} if sacado or agregado else None


def revisadas(story: Story) -> Story:
    """D27: «Listo, ya las revisé»: sin la marca."""
    d = story.direction
    if d is None or not d.idea_sin_revisar:
        return story
    return story.model_copy(update={"direction": d.model_copy(update={"idea_sin_revisar": ""})})


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
        sacado, agregado = self.cambio(story)
        return self.templates.load("authoring_revisor.md").format(
            idea=context.idea(story),
            sacado=self._lista(sacado),
            agregado=self._lista(agregado),
            respuestas="\n".join(rows),
        )

    @staticmethod
    def cambio(story: Story) -> tuple[list[str], list[str]]:
        """S4: qué oraciones se sacaron y cuáles se agregaron desde la última ronda."""
        antes = story.direction.idea_preguntas if story.direction else ""
        return context.lo_que_cambio(antes, context.idea(story))

    def _lista(self, oraciones: list[str]) -> str:
        t = self.templates.fragment
        if not oraciones:
            return t("asistente/revisor/nada")
        return "\n".join(t("asistente/revisor/oracion", oracion=o) for o in oraciones)

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
        cambiadas = [*sum(self.cambio(story), [])]
        out = []
        for r in result.revisiones:
            item = by_id.pop(r.criterio, None)
            if item is None:
                continue
            motivo = " ".join(r.motivo.split())
            # S4: se marca solo si cita una oración que de verdad cambió (gemma marcaba
            # respuestas que solo suman detalles que la idea no dice).
            choca = not r.coincide and motivo and _cita(r.cambio, cambiadas)
            updated = (
                workshop_rules.mark_no_coincide(item, motivo)
                if choca
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


def _cita(cita: str, oraciones: list[str]) -> bool:
    """¿La cita es (o está en, o contiene) una de las oraciones que cambiaron?"""
    key = " ".join(workshop_rules.normalize(cita).split())
    if len(key) < 8:
        return False
    for o in oraciones:
        other = " ".join(workshop_rules.normalize(o).split())
        if key in other or (other and other in key):
            return True
    return False


def _output_model(criteria: list[str]) -> type[BaseModel]:
    revision = create_model(
        "RevisionRespuesta",
        criterio=(Literal[tuple(criteria)], ...),
        coincide=(bool, ...),
        cambio=(str, ...),
        motivo=(str, ...),
    )
    return create_model("RevisionDeRespuestas", revisiones=(list[revision], ...))
