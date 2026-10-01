"""Contexto de la historia que reciben los roles del asistente (Spec-530).

Lleva el objetivo y la dirección del autor (sin eso las preguntas no se atan a lo
que quiere contar), no la teoría: los criterios ya vienen como preguntas concretas.

Spec-620: el texto vive en `config/prompts_generation/fragments/asistente/`; las funciones
que arman texto reciben el `TemplateLoader` de quien las llama.
"""

from src.application.services.authoring import catalog
from src.application.services.template_loader import TemplateLoader
from src.domain.models import CriterionStatus, Story, WorkshopItem, WorkshopLevel


def objective(templates: TemplateLoader) -> str:
    """Para qué es todo esto: el objetivo que reciben los roles del asistente."""
    return templates.fragment("asistente/objetivo")


def protagonist(story: Story) -> str:
    cast = story.personajes_full or []
    return cast[0].get("name", "") if cast else story.protagonista.split(":")[0].strip()


def narrator(story: Story) -> str:
    cfg = story.narrator_config or {}
    return cfg.get("storyteller_name") or protagonist(story)


def story_block(story: Story, templates: TemplateLoader) -> str:
    """Qué historia es y qué quiere el autor."""
    t = templates.fragment
    d = story.direction
    lines = [t("asistente/historia/titulo", titulo=story.title)]
    genre = " / ".join(x for x in (story.genero, story.subgenero) if x)
    if genre:
        lines.append(t("asistente/historia/tipo", genero=genre))
    premise = (d.premise if d and d.premise else story.sinopsis).strip()
    lines.append(t("asistente/historia/de_que_trata", premisa=premise))
    lines.append(t("asistente/historia/protagonista", protagonista=story.protagonista))
    lines.append(t("asistente/historia/quien_lo_cuenta", narrador=narrator(story)))
    if d:
        if d.effect:
            effect = (
                d.effect_other
                if d.effect == "otro"
                else catalog.label_of(catalog.effects(), d.effect)
            )
            lines.append(t("asistente/historia/efecto", efecto=effect))
        if d.telling:
            telling = catalog.label_of(catalog.tellings(), d.telling)
            lines.append(t("asistente/historia/como_lo_cuenta", como=telling))
        if d.ending:
            fixed = t("asistente/historia/final_decidido") if d.ending_intentional else ""
            lines.append(t("asistente/historia/como_termina", final=d.ending, decidido=fixed))
    cast = [p for p in story.personajes_full or [] if p.get("name")]
    if len(cast) > 1:
        people = "; ".join(_person(p) for p in cast)
        lines.append(t("asistente/historia/personajes", personajes=people))
    return "\n".join(lines)


def _person(p: dict) -> str:
    extra = p.get("relation") or p.get("role") or ""
    return f"{p['name']} ({extra})" if extra else p["name"]


def decisions(story: Story) -> list[tuple[str, str, str]]:
    """Decisiones del autor en el taller: (id, nombre, texto). Respondidas o intencionales."""
    out = []
    for item in _direction_items(story):
        c = catalog.criterion(item.criterion)
        if (
            c
            and item.answer
            and item.status in (CriterionStatus.CUMPLE, CriterionStatus.INTENCIONAL)
        ):
            out.append((c.id, c.for_story(protagonist(story)).nombre, item.answer))
    return out


def decisions_block(story: Story, templates: TemplateLoader) -> str:
    """Historial del taller como pregunta → respuesta: sin la pregunta, una respuesta
    corta («su hija») no se entiende."""
    t = templates.fragment
    by_id = {w.criterion: w for w in _direction_items(story)}
    rows = []
    for cid, nombre, texto in decisions(story):
        item = by_id[cid]
        c = catalog.criterion(cid)
        if c and c.acto:  # Spec-580 D2
            nombre += t("asistente/decisiones/va_en_acto", acto=c.acto)
        if item.status == CriterionStatus.INTENCIONAL:
            rows.append(t("asistente/decisiones/intencional", id=cid, nombre=nombre, texto=texto))
        elif item.asked:
            rows.append(
                t(
                    "asistente/decisiones/con_pregunta",
                    id=cid,
                    nombre=nombre,
                    pregunta=item.asked[-1],
                    texto=texto,
                )
            )
        else:
            rows.append(t("asistente/decisiones/respondida", id=cid, nombre=nombre, texto=texto))
    if not rows:
        return t("asistente/decisiones/vacio")
    return "\n".join(rows)


def pending_block(story: Story, templates: TemplateLoader) -> str:
    """Preguntas ya hechas que el autor todavía no respondió (no hay que reformularlas)."""
    rows = [
        templates.fragment("asistente/pendientes/pendiente", id=w.criterion, pregunta=w.question)
        for w in _direction_items(story)
        if w.question and not w.answer and w.status != CriterionStatus.INTENCIONAL
    ]
    return "\n".join(rows) if rows else templates.fragment("asistente/pendientes/vacio")


def _direction_items(story: Story) -> list[WorkshopItem]:
    return [w for w in story.workshop if w.level == WorkshopLevel.DIRECCION]


def effect_recipe(story: Story) -> tuple[str, str]:
    """Spec-560 A5: (nombre del efecto, receta para la escaleta). «Otro» usa el texto del autor."""
    d = story.direction
    if not d or not d.effect:
        return "", ""
    if d.effect == "otro":
        return (d.effect_other, d.effect_other) if d.effect_other.strip() else ("", "")
    option = next((o for o in catalog.effects() if o.id == d.effect), None)
    return (option.label, option.planner) if option and option.planner else ("", "")


def effect_block(story: Story, templates: TemplateLoader, verifier: bool = False) -> str:
    name, recipe = effect_recipe(story)
    if not recipe:
        return ""
    role = "verificador" if verifier else "planificador"
    return templates.fragment(f"asistente/efecto/{role}", nombre=name, receta=recipe) + "\n\n"
