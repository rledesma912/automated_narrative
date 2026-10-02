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
from src.domain.models import ActOutline, OutlineWarning, Story, normalize_key
from src.messages import message

ROLE = "verificador"
MAX_LLM_WARNINGS_PER_ACT = 2
MAX_WARNINGS_PER_ACT = 3  # visibles; reglas primero (más concretas), después el LLM


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
        # Spec-550 H10: lo que el autor ignoró no vuelve (ni de regla ni de la IA).
        dismissed = {a.number: a.dismissed_keys() for a in outline}
        warnings = rule_warnings(story, outline, dismissed)
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
            if not (w.acto in numbers and w.aviso.strip()):
                continue
            warning = OutlineWarning.from_ai(w.aviso)
            if (
                warning.key in dismissed[w.acto]
                or per_act.get(w.acto, 0) >= MAX_LLM_WARNINGS_PER_ACT
            ):
                continue
            per_act[w.acto] = per_act.get(w.acto, 0) + 1
            warnings.setdefault(w.acto, []).append(warning)

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
                        "warnings": _dedup(warnings.get(act.number, []))[:MAX_WARNINGS_PER_ACT]
                        + [w for w in act.warnings if w.dismissed],
                        "decisions": used,
                    }
                )
            )
        used_anywhere = {d for a in acts for d in a.decisions}
        missing = [d for d in decided if d not in used_anywhere]
        return Verification(acts, missing, elapsed)

    def _prompt(self, story: Story, outline: list[ActOutline]) -> str:
        t = self.templates
        protagonist = context.protagonist(story)
        return t.load("authoring_verifier.md").format(
            historia=context.story_block(story, t),
            decisiones=context.decisions_block(story, t),
            elenco=", ".join(cast_names(story)) or t.fragment("asistente/verificador/elenco_vacio"),
            escaleta="\n\n".join(
                self._act_text(a, protagonist, _act_rules(story, a.number)) for a in outline
            ),
            efecto=context.effect_block(story, t, verifier=True),
            descartados="\n".join(
                t.fragment("asistente/aviso_de_acto", numero=a.number, aviso=w.text)
                for a in outline
                for w in a.warnings
                if w.dismissed
            )
            or t.fragment("asistente/verificador/descartados_vacio"),
        )

    def _act_text(self, a: ActOutline, protagonist: str = "", rules: list[str] = ()) -> str:
        """El acto como lo lee la revisión."""
        t = self.templates.fragment
        lines = [
            t(
                "asistente/verificador/acto/titulo_con_escenario",
                numero=a.number,
                escenario=a.scenario,
            )
            if a.scenario
            else t("asistente/verificador/acto/titulo", numero=a.number)
        ]
        if a.bridge:
            lines.append(t("asistente/verificador/acto/como_llega", puente=a.bridge))
        if a.goal:
            lines.append(t("asistente/verificador/acto/quiere", objetivo=a.goal))
        # Spec-630 B11: quiénes están, cómo cambia y las reglas del acto (antes solo los
        # veían las reglas sin IA: elenco y `sin_cambio`).
        if a.on_stage:
            lines.append(t("asistente/verificador/acto/en_escena", nombres=", ".join(a.on_stage)))
        lines += [f"- {e}" for e in a.events]
        if a.change_from or a.change_to:
            lines.append(t("asistente/verificador/acto/cambia", de=a.change_from, a=a.change_to))
        if rules:
            lines.append(t("asistente/verificador/acto/reglas", reglas="; ".join(rules)))
        if a.held_back:
            reveal = (
                t("asistente/verificador/acto/se_revela", acto=a.reveal_act) if a.reveal_act else ""
            )
            lines.append(
                t("asistente/verificador/acto/no_se_cuenta", secreto=a.held_back, revela=reveal)
            )
        if a.decisions:
            names = [
                c.for_story(protagonist).nombre
                for c in catalog.direction_criteria()
                if c.id in a.decisions
            ]
            lines.append(t("asistente/verificador/acto/usa", decisiones=", ".join(names)))
        return "\n".join(lines)


def _act_rules(story: Story, number: int) -> list[str]:
    """Las reglas que el autor ancló a este acto (las globales no son de ningún acto)."""
    return [r.content for r in story.typed_rules if r.applies_to_beat == number]


def rule_warnings(
    story: Story, outline: list[ActOutline], dismissed: dict[int, set[str]] | None = None
) -> dict[int, list[OutlineWarning]]:
    """Avisos que no necesitan al LLM, con clave estable por tema (Spec-550 H10).

    `dismissed` son las claves que el autor ignoró en cada acto: esos avisos no se
    vuelven a dar, y un aviso que junta siembras se arma sin las ignoradas.
    """
    dismissed = dismissed or {}
    out: dict[int, list[OutlineWarning]] = {}

    def add(n: int, key: str, text: str) -> None:
        if key not in dismissed.get(n, set()):
            out.setdefault(n, []).append(OutlineWarning(text=text, key=key, source="regla"))

    cast = {workshop_rules.normalize(n) for n in cast_names(story)}
    threats = {workshop_rules.normalize(e.name) for e in story.entities if e.name}
    prota = context.protagonist(story) or message("verifier.protagonista")
    for act in outline:
        if not act.events:
            add(act.number, "sin_hechos", message("verifier.sin_hechos"))
        if act.number > 1 and not act.bridge.strip():
            add(act.number, "sin_puente", message("verifier.sin_puente"))
        if act.change_from and workshop_rules.normalize(
            act.change_from
        ) == workshop_rules.normalize(act.change_to):
            add(act.number, "sin_cambio", message("verifier.sin_cambio", protagonista=prota))
        for name in act.on_stage:
            key = workshop_rules.normalize(name.split("(")[0])
            if key and key not in cast and key not in threats:
                add(
                    act.number,
                    f"elenco:{key}",
                    message("verifier.elenco", nombre=name),
                )
        if act.held_back.strip() and not act.number < act.reveal_act <= 5:
            add(act.number, "sin_revelacion", message("verifier.sin_revelacion"))
        later = [a for a in outline if a.number > act.number]
        loose = [
            s
            for s in act.seeds
            if not any(_mentions(p, s) for a in later for p in a.payoffs)
            and f"siembra:{normalize_key(s)}" not in dismissed.get(act.number, set())
        ]
        key = "|".join(f"siembra:{normalize_key(s)}" for s in loose)
        if len(loose) == 1:
            add(act.number, key, message("verifier.siembra", siembra=loose[0]))
        elif loose:
            names = ", ".join(f"«{s}»" for s in loose)
            add(act.number, key, message("verifier.siembras", siembras=names))
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


def _dedup(items: list[OutlineWarning]) -> list[OutlineWarning]:
    seen, out = set(), []
    for i in items:
        key = workshop_rules.normalize(i.text)
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out
