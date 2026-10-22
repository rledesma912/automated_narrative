"""El final sale de la idea (Spec-690): «¿Cómo termina?» ya no está en «Tu idea».

Antes del Consultor o del Planificador (siempre dentro de un comando de la persona), la
IA se fija si «¿De qué trata?» cuenta cómo termina y marca dónde empieza el final; el
código lo corta desde ahí hasta el final de la idea (D1: lo medido en §1.3). Nunca
inventa: si la oración no está en la idea, el final queda para preguntar.

Se guarda en el criterio `final` de «Preguntas», decidido (`intencional`) y con la marca
`·de_la_idea` (D11). No corre si la autora ya decidió el final, si pidió que se lo
pregunten (D13) o si el final sacado sigue en la idea (D12).
"""

from pydantic import BaseModel

from src.application.services.authoring import molde, workshop_rules
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import CriterionStatus, Story, WorkshopItem, WorkshopLevel

ROLE = "consultor"
CRITERION = "final"
_MATCH_CHARS = 60  # alcanza con el principio de la oración para ubicarla en la idea


class FinalDeLaIdeaSalida(BaseModel):
    cuenta_final: bool
    inicio: str


def _flat(text: str) -> str:
    return " ".join(text.split())


def cut(idea: str, inicio: str) -> str:
    """Desde la oración `inicio` hasta el final de la idea; "" si no está en la idea."""
    flat, start = _flat(idea), _flat(inicio).strip("\"'«»“”")
    if not start:
        return ""
    key = start[:_MATCH_CHARS]
    pos = flat.find(key)
    if pos < 0:
        pos = flat.lower().find(key.lower())
    return flat[pos:].strip() if pos >= 0 else ""


def _item(story: Story) -> WorkshopItem | None:
    return next(
        (
            w
            for w in story.workshop
            if w.level == WorkshopLevel.DIRECCION and w.criterion == CRITERION
        ),
        None,
    )


def needs_it(story: Story) -> bool:
    """¿Hay que buscar el final en la idea? (sin llamar a la IA)."""
    idea = story.direction.premise.strip() if story.direction else ""
    if not idea or CRITERION not in molde.for_story(story).ids:
        return False
    item = _item(story)
    if item and workshop_rules.FINAL_PREGUNTAR in item.asked:
        return False  # D13: pidió que se lo pregunten
    decided = item and item.answer.strip() and item.status != CriterionStatus.FALTA
    if decided:
        # D12: el sacado de la idea se vuelve a buscar solo si la idea ya no lo cuenta.
        from_idea = workshop_rules.DE_LA_IDEA in item.asked
        return from_idea and _flat(item.answer) not in _flat(idea)
    return not story.direction.ending.strip()  # el «¿Cómo termina?» viejo ya lo decide


class FinalDeLaIdea:
    def __init__(self, llm: LLMProvider, templates: TemplateLoader | None = None):
        self.llm = llm
        self.templates = templates or TemplateLoader()

    def prompt(self, story: Story) -> str:
        return self.templates.load("authoring_final.md").format(idea=story.direction.premise)

    async def ensure(self, story: Story) -> WorkshopItem | None:
        """El criterio `final` actualizado para guardar, o None si no cambia nada."""
        if not needs_it(story):
            return None
        result, _ = await generate_structured(
            self.llm,
            role=ROLE,
            prompt=self.prompt(story),
            system_prompt=self.templates.load("authoring_final_system.md"),
            output=FinalDeLaIdeaSalida,
        )
        ending = cut(story.direction.premise, result.inicio) if result.cuenta_final else ""
        item = _item(story) or WorkshopItem(criterion=CRITERION, round=1)
        asked = [a for a in item.asked if a != workshop_rules.DE_LA_IDEA]
        if not ending:
            if workshop_rules.DE_LA_IDEA not in item.asked:
                return None  # nada que guardar: el Consultor lo pregunta
            # D12: la idea cambió y ya no cuenta el final: vuelve a ser una pregunta.
            update = {"status": CriterionStatus.FALTA, "answer": "", "asked": asked}
            return item.model_copy(update=update)
        return item.model_copy(
            update={
                "status": CriterionStatus.INTENCIONAL,
                "answer": ending,
                "question": "",
                "options": [],
                "asked": [*asked, workshop_rules.DE_LA_IDEA],
            }
        )


def apply(story: Story, item: WorkshopItem | None) -> Story:
    """La historia con el criterio actualizado (para seguir sin releer la base)."""
    if item is None:
        return story
    others = [
        w for w in story.workshop if not (w.level == item.level and w.criterion == item.criterion)
    ]
    return story.model_copy(update={"workshop": [*others, item]})
