"""Verificador de la escaleta (Spec-530 §5.3): señala problemas; no corrige solo.

Primero reglas determinísticas (sin LLM), después una revisión del LLM para lo que
necesita leer: hechos repetidos o adelantados, secretos sin revelar, decisiones
que el Planificador dice usar pero no están en los hechos, personajes fuera del elenco.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from src.application.services.authoring import catalog, context, workshop_rules
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import ActOutline, Story

ROLE = "verificador"
MAX_LLM_WARNINGS_PER_ACT = 2
MAX_WARNINGS_PER_ACT = 3  # reglas primero (más concretas), después el LLM


class AvisoActo(BaseModel):
    acto: int
    aviso: str


class UbicacionDecision(BaseModel):
    decision: str
    acto: int  # 0 = no aparece en ningún hecho


class Revision(BaseModel):
    decisiones: list[UbicacionDecision]
    avisos: list[AvisoActo]


@dataclass(frozen=True)
class Verification:
    outline: list[ActOutline]  # con `warnings` y `decisions` al día
    missing_decisions: list[str]  # ids de decisiones que no aparecen en ningún acto
    elapsed_s: float


class OutlineVerifier:
    def __init__(self, llm: LLMProvider, templates: TemplateLoader | None = None):
        self.llm = llm
        self.templates = templates or TemplateLoader()

    async def verify(self, story: Story, outline: list[ActOutline]) -> Verification:
        warnings = rule_warnings(story, outline)
        result, elapsed = await generate_structured(
            self.llm,
            role=ROLE,
            prompt=self._prompt(story, outline),
            system_prompt=self.templates.load("authoring_verifier_system.md"),
            output=Revision,
        )
        numbers = {a.number for a in outline}
        per_act: dict[int, int] = {}
        for w in result.avisos:
            if (
                w.acto in numbers
                and w.aviso.strip()
                and per_act.get(w.acto, 0) < MAX_LLM_WARNINGS_PER_ACT
            ):
                per_act[w.acto] = per_act.get(w.acto, 0) + 1
                warnings.setdefault(w.acto, []).append(" ".join(w.aviso.split()))

        decided = [cid for cid, _, _ in context.decisions(story)]
        # La ubicación que da la revisión (leyendo los hechos) manda sobre las etiquetas
        # del Planificador; lo que la revisión no menciona conserva su etiqueta.
        located = {u.decision: u.acto for u in result.decisiones if u.decision in decided}
        if story.direction and story.direction.ending_intentional and "final" in decided:
            located["final"] = max(numbers)  # el final del autor es el del último acto, siempre
        acts = []
        for act in outline:
            used = [d for d in act.decisions if d not in located]
            used += [d for d, n in located.items() if n == act.number and d not in used]
            acts.append(
                act.model_copy(
                    update={
                        "warnings": _dedup(warnings.get(act.number, []))[:MAX_WARNINGS_PER_ACT],
                        "decisions": used,
                    }
                )
            )
        used_anywhere = {d for a in acts for d in a.decisions}
        missing = [d for d in decided if d not in used_anywhere]
        return Verification(acts, missing, elapsed)

    def _prompt(self, story: Story, outline: list[ActOutline]) -> str:
        return self.templates.load("authoring_verifier.md").format(
            historia=context.story_block(story),
            decisiones=context.decisions_block(story),
            elenco=", ".join(cast_names(story)) or "(solo quien narra)",
            escaleta="\n\n".join(_act_text(a) for a in outline),
        )


def rule_warnings(story: Story, outline: list[ActOutline]) -> dict[int, list[str]]:
    """Avisos que no necesitan al LLM."""
    out: dict[int, list[str]] = {}

    def add(n: int, text: str) -> None:
        out.setdefault(n, []).append(text)

    cast = {workshop_rules.normalize(n) for n in cast_names(story)}
    threats = {workshop_rules.normalize(e.name) for e in story.entities if e.name}
    for act in outline:
        if not act.events:
            add(act.number, "El acto no tiene hechos: ¿qué pasa acá?")
        if act.change_from and workshop_rules.normalize(
            act.change_from
        ) == workshop_rules.normalize(act.change_to):
            add(act.number, "El acto termina igual que empieza: ¿qué cambia para el protagonista?")
        for name in act.on_stage:
            key = workshop_rules.normalize(name.split("(")[0])
            if key and key not in cast and key not in threats:
                add(
                    act.number,
                    f"«{name}» está en escena y no en el elenco: ¿lo sumamos como personaje?",
                )
        later = [a for a in outline if a.number > act.number]
        loose = [s for s in act.seeds if not any(_mentions(p, s) for a in later for p in a.payoffs)]
        if len(loose) == 1:
            add(act.number, f"«{loose[0]}» se siembra acá y ningún acto posterior lo retoma.")
        elif loose:
            names = ", ".join(f"«{s}»" for s in loose)
            add(act.number, f"{names} se siembran acá y ningún acto posterior los retoma.")
    return out


def cast_names(story: Story) -> list[str]:
    names = [p["name"] for p in story.personajes_full or [] if p.get("name")]
    narrator = context.narrator(story)
    if narrator and narrator not in names:
        names.insert(0, narrator)
    return names


def _mentions(a: str, b: str) -> bool:
    na, nb = workshop_rules.normalize(a), workshop_rules.normalize(b)
    return na in nb or nb in na or workshop_rules.similar(a, b)


def _act_text(a: ActOutline) -> str:
    lines = [f"ACTO {a.number}" + (f" — {a.scenario}" if a.scenario else "")]
    if a.goal:
        lines.append(f"Quiere: {a.goal}")
    lines += [f"- {e}" for e in a.events]
    if a.held_back:
        lines.append(f"Se guarda para después: {a.held_back}")
    if a.decisions:
        names = [c.nombre for c in catalog.direction_criteria() if c.id in a.decisions]
        lines.append("Dice que usa: " + ", ".join(names))
    return "\n".join(lines)


def _dedup(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        key = workshop_rules.normalize(i)
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out
