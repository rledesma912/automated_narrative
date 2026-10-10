"""La IA sugiere la clase de historia (Spec-670 D1): job `suggest_form`.

Lee la idea y elige una forma del catálogo (`config/moldes/`) con un motivo; si no es
ninguna, «otra» con cómo es la historia. Solo se guarda: la persona la ve en «Tu idea»
y la confirma o la cambia.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import create_model

from src.application.services.authoring import context, molde
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import Direction, Story

ROLE = "consultor"


@dataclass(frozen=True)
class FormSuggestion:
    form: str
    reason: str
    arc: str  # solo con «otra»


class FormSuggester:
    def __init__(self, llm: LLMProvider, templates: TemplateLoader | None = None):
        self.llm = llm
        self.templates = templates or TemplateLoader()

    async def suggest(self, story: Story) -> tuple[FormSuggestion, float]:
        formas = molde.catalogo().formas
        output = create_model(
            "SugerenciaForma",
            forma=(Literal[tuple(f.id for f in formas)], ...),
            motivo=(str, ...),
            arco=(str, ...),
        )
        result, elapsed = await generate_structured(
            self.llm,
            role=ROLE,
            prompt=self.prompt(story),
            system_prompt=self.templates.load("authoring_form_system.md"),
            output=output,
        )
        forma = molde.catalogo().forma(result.forma)
        arc = " ".join(result.arco.split()) if forma and forma.arco_del_autor else ""
        return FormSuggestion(result.forma, " ".join(result.motivo.split()), arc), elapsed

    def prompt(self, story: Story) -> str:
        opciones = "\n".join(
            self.templates.fragment("asistente/forma_opcion", id=f.id, nombre=f.nombre, arco=f.arco)
            for f in molde.catalogo().formas
        )
        return self.templates.load("authoring_form.md").format(
            historia=context.story_block(story, self.templates), formas=opciones
        )


def apply(direction: Direction | None, s: FormSuggestion) -> Direction:
    """Lo que se guarda: la sugerencia siempre; la forma solo si la persona no había
    elegido una (si eligió, la sugerencia se ve al lado y decide ella); con «otra», el
    arco propuesto si el campo estaba vacío."""
    d = direction or Direction()
    update = {"form_suggested": s.form, "form_reason": s.reason}
    if not d.form:
        update["form"] = s.form
    if s.arc and not d.form_other.strip():
        update["form_other"] = s.arc
    return d.model_copy(update=update)
