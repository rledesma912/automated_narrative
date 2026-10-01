"""Planificador de la escaleta (Spec-530 §5.2): reparte la historia en 5 actos."""

import re

from pydantic import BaseModel, model_validator

from src.application.services.authoring import context
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.core_messages import message
from src.application.services.prompt_builder import PromptBuilder
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import ActOutline, Story

ROLE = "planificador"
NUM_ACTS = 5


class ActoPlan(BaseModel):
    numero: int
    como_llega: str  # Spec-560 A1: "" en el acto 1
    objetivo: str
    hechos: list[str]
    cambio_de: str
    cambio_a: str
    escenario: str
    en_escena: list[str]
    se_guarda: str
    se_revela_en: int  # Spec-560 A4: acto que revela lo guardado (0 si no se guarda nada)
    siembra: list[str]
    retoma: list[str]
    decisiones: list[str]


class Escaleta(BaseModel):
    actos: list[ActoPlan]

    @model_validator(mode="after")
    def _cinco_actos(self) -> "Escaleta":
        numbers = sorted(a.numero for a in self.actos)
        if numbers != list(range(1, NUM_ACTS + 1)):
            raise ValueError(message("job.escaleta_sin_actos", actos=numbers))
        empty = [a.numero for a in self.actos if not [h for h in a.hechos if h.strip()]]
        if empty:
            raise ValueError(message("job.escaleta_sin_hechos", actos=empty))
        return self


class OutlinePlanner:
    def __init__(
        self,
        llm: LLMProvider,
        templates: TemplateLoader | None = None,
        prompt_builder: PromptBuilder | None = None,
    ):
        self.llm = llm
        self.templates = templates or TemplateLoader()
        self.prompt_builder = prompt_builder or PromptBuilder()

    async def plan(self, story: Story) -> tuple[list[ActOutline], float]:
        """Arma la escaleta completa (reemplaza la anterior)."""
        result, elapsed = await generate_structured(
            self.llm,
            role=ROLE,
            prompt=self._prompt(story),
            system_prompt=self.templates.load("authoring_planner_system.md"),
            output=Escaleta,
        )
        valid = {cid for cid, _, _ in context.decisions(story)}
        acts = [_to_outline(a, valid) for a in sorted(result.actos, key=lambda a: a.numero)]
        # Spec-570 D2: la sinopsis por acto del autor queda con su acto (vuelve al exportar).
        synopsis = {a.number: a.synopsis for a in story.outline if a.synopsis}
        acts = [
            a.model_copy(update={"synopsis": synopsis[a.number]}) if a.number in synopsis else a
            for a in acts
        ]
        if story.direction and story.direction.ending_intentional and "final" in valid:
            # El final decidido por el autor es, por definición, el del último acto.
            last = acts[-1]
            if "final" not in last.decisions:
                acts[-1] = last.model_copy(update={"decisions": [*last.decisions, "final"]})
        return acts, elapsed

    def _prompt(self, story: Story) -> str:
        scenarios = "; ".join(
            f"{s.name}: {s.description}" if s.description else s.name for s in story.scenarios
        )
        t = self.templates
        return t.load("authoring_planner.md").format(
            objetivo=context.objective(t),
            historia=context.story_block(story, t),
            decisiones=context.decisions_block(story, t),
            borradores=self._drafts_block(story),
            problemas=self._problems_block(story),
            efecto=context.effect_block(story, t),
            escenarios=scenarios or t.fragment("asistente/planificador/escenarios_vacio"),
            actos=self._acts_block(story),
        )

    def _acts_block(self, story: Story) -> str:
        ending_fixed = bool(story.direction and story.direction.ending_intentional)
        has_secret = any(cid == "historia_secreta" for cid, _, _ in context.decisions(story))
        t = self.templates.fragment
        lines = []
        for n in range(1, NUM_ACTS + 1):
            info = self.prompt_builder.get_beat_info(n)
            intent = info.get("intent", "")
            if n == NUM_ACTS and ending_fixed:
                intent = t("asistente/planificador/final_del_autor")
            if n == NUM_ACTS - 1 and has_secret:
                intent += t("asistente/planificador/historia_secreta")
            lines.append(
                t(
                    "asistente/planificador/acto",
                    numero=n,
                    nombre=info.get("label") or info.get("name", ""),
                    intensidad=info.get("intensity", ""),
                    intencion=intent,
                )
            )
        return "\n".join(lines)

    def _drafts_block(self, story: Story) -> str:
        """Spec-570 D2: lo que el autor escribió para cada acto (YAML viejo), como guía."""
        t = self.templates.fragment
        lines = [
            t("asistente/planificador/borrador", numero=a.number, sinopsis=a.synopsis)
            for a in sorted(story.outline, key=lambda a: a.number)
            if a.synopsis
        ]
        if not lines:
            return ""
        return t("asistente/planificador/borradores") + "\n" + "\n".join(lines) + "\n\n"

    def _problems_block(self, story: Story) -> str:
        """Spec-560 A6: al rearmar, los avisos visibles de la escaleta anterior (no los
        ignorados)."""
        t = self.templates.fragment
        lines = [
            t("asistente/aviso_de_acto", numero=a.number, aviso=w.text)
            for a in sorted(story.outline, key=lambda a: a.number)
            if not a.draft
            for w in a.visible_warnings()
        ]
        if not lines:
            return ""
        return t("asistente/planificador/problemas") + "\n" + "\n".join(lines) + "\n\n"


def _scenario_name(name: str) -> str:
    """«Ruta 36 (regreso)» es el mismo lugar que «Ruta 36», y «María (aparición)» la misma
    María: sin agregados entre paréntesis."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", " ".join(name.split())) or name.strip()


def _clean(items: list[str]) -> list[str]:
    return [" ".join(i.split()) for i in items if i and i.strip()]


def _to_outline(a: ActoPlan, valid_decisions: set[str]) -> ActOutline:
    return ActOutline(
        number=a.numero,
        bridge="" if a.numero == 1 else " ".join(a.como_llega.split()),
        goal=a.objetivo.strip(),
        events=_clean(a.hechos),
        change_from=a.cambio_de.strip(),
        change_to=a.cambio_a.strip(),
        scenario=_scenario_name(a.escenario),
        on_stage=list(dict.fromkeys(_scenario_name(n) for n in _clean(a.en_escena))),
        held_back=a.se_guarda.strip(),
        reveal_act=a.se_revela_en if a.se_guarda.strip() and a.numero < a.se_revela_en <= 5 else 0,
        seeds=_clean(a.siembra),
        payoffs=_clean(a.retoma),
        decisions=[d for d in _clean(a.decisiones) if d in valid_decisions],
    )
