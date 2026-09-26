"""Planificador de la escaleta (Spec-530 §5.2): reparte la historia en 5 actos."""

import re

from pydantic import BaseModel, model_validator

from src.application.services.authoring import context
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.prompt_builder import PromptBuilder
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import ActOutline, Story

ROLE = "planificador"
NUM_ACTS = 5
_ACT_NAMES = {
    "exposicion": "Exposición",
    "accion_ascendente": "Acción ascendente",
    "climax": "Clímax",
    "accion_descendente": "Acción descendente",
    "desenlace": "Desenlace",
}


class ActoPlan(BaseModel):
    numero: int
    objetivo: str
    hechos: list[str]
    cambio_de: str
    cambio_a: str
    escenario: str
    en_escena: list[str]
    se_guarda: str
    siembra: list[str]
    retoma: list[str]
    decisiones: list[str]


class Escaleta(BaseModel):
    actos: list[ActoPlan]

    @model_validator(mode="after")
    def _cinco_actos(self) -> "Escaleta":
        numbers = sorted(a.numero for a in self.actos)
        if numbers != list(range(1, NUM_ACTS + 1)):
            raise ValueError(f"la escaleta tiene que tener los actos 1 a 5 (llegaron {numbers})")
        empty = [a.numero for a in self.actos if not [h for h in a.hechos if h.strip()]]
        if empty:
            raise ValueError(f"actos sin hechos: {empty}")
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
        return self.templates.load("authoring_planner.md").format(
            objetivo=context.OBJETIVO,
            historia=context.story_block(story),
            decisiones=context.decisions_block(story),
            escenarios=scenarios or "(ninguno todavía)",
            actos=self._acts_block(story),
        )

    def _acts_block(self, story: Story) -> str:
        ending_fixed = bool(story.direction and story.direction.ending_intentional)
        has_secret = any(cid == "historia_secreta" for cid, _, _ in context.decisions(story))
        lines = []
        for n in range(1, NUM_ACTS + 1):
            info = self.prompt_builder.get_beat_info(n)
            name = _ACT_NAMES.get(info.get("name", ""), info.get("name", ""))
            intent = info.get("intent", "")
            if n == NUM_ACTS and ending_fixed:
                intent = "cerrar la historia con el final que decidió el autor"
            if n == NUM_ACTS - 1 and has_secret:
                intent += "; acá el protagonista descubre o confiesa la historia secreta"
            lines.append(f"{n}. {name} (intensidad {info.get('intensity', '')}): {intent}")
        return "\n".join(lines)


def _scenario_name(name: str) -> str:
    """«Ruta 36 (regreso)» es el mismo lugar que «Ruta 36», y «María (aparición)» la misma
    María: sin agregados entre paréntesis."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", " ".join(name.split())) or name.strip()


def _clean(items: list[str]) -> list[str]:
    return [" ".join(i.split()) for i in items if i and i.strip()]


def _to_outline(a: ActoPlan, valid_decisions: set[str]) -> ActOutline:
    return ActOutline(
        number=a.numero,
        goal=a.objetivo.strip(),
        events=_clean(a.hechos),
        change_from=a.cambio_de.strip(),
        change_to=a.cambio_a.strip(),
        scenario=_scenario_name(a.escenario),
        on_stage=list(dict.fromkeys(_scenario_name(n) for n in _clean(a.en_escena))),
        held_back=a.se_guarda.strip(),
        seeds=_clean(a.siembra),
        payoffs=_clean(a.retoma),
        decisions=[d for d in _clean(a.decisiones) if d in valid_decisions],
    )
