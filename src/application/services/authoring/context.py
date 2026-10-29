"""Contexto de la historia que reciben los roles del asistente (Spec-530).

Lleva el objetivo y la dirección del autor (sin eso las preguntas no se atan a lo
que quiere contar), no la teoría: los criterios ya vienen como preguntas concretas.

Spec-620: el texto vive en `config/prompts_generation/fragments/asistente/`; las funciones
que arman texto reciben el `TemplateLoader` de quien las llama.
"""

import difflib
import re

from src.application.services.authoring import catalog, molde, workshop_rules
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.template_loader import TemplateLoader
from src.domain.models import CriterionStatus, Story, WorkshopItem, WorkshopLevel


def objective(templates: TemplateLoader, story: Story) -> str:
    """Para qué es todo esto: el objetivo que reciben los roles del asistente (con la
    cantidad de actos y de palabras de la estructura de la historia, Spec-650)."""
    estructura = BeatSpecRepository().estructura(story.structure)
    return templates.fragment(
        "asistente/objetivo", num_actos=estructura.num_actos, palabras=estructura.palabras_total
    )


def author_ending(story: Story) -> str:
    """Spec-690 D15: el final que decidió la autora, de un solo lugar. Es la respuesta
    **a propósito** del criterio `final` de «Preguntas» (sacada de la idea, el «¿Cómo
    termina?» viejo o un cambio de la autora sobre esos); si no hay, `Direction.ending`.

    Una respuesta común del criterio («Inquietud», una opción del Consultor) no es el
    final: la pregunta es por la marca que deja (D17), y queda como una decisión más."""
    item = next((w for w in _direction_items(story) if w.criterion == "final"), None)
    if item and item.answer.strip() and item.status == CriterionStatus.INTENCIONAL:
        return item.answer.strip()
    return story.direction.ending.strip() if story.direction else ""


def idea(story: Story) -> str:
    """La idea que lee la IA: «¿De qué trata?» o, en las importadas, la sinopsis (como
    `story_block`)."""
    d = story.direction
    return (d.premise if d and d.premise else story.sinopsis).strip()


def _misma(a: str, b: str) -> bool:
    """Spec-700 D13: mayúsculas, signos y espacios no cuentan (retocar una coma no es
    cambiar la idea)."""

    def norm(text: str) -> str:
        return " ".join(workshop_rules.normalize(text).split())

    return norm(a) == norm(b)


def idea_cambio(story: Story) -> dict[str, bool]:
    """D12/D14: ¿cambió la idea desde que la leyeron «Preguntas» y «Los actos»? Sin sello no
    se sabe, y no se avisa (las historias de antes de la 700). «Los actos», solo si hay."""
    d = story.direction
    now = idea(story)
    preguntas = bool(d and d.idea_preguntas and not _misma(d.idea_preguntas, now))
    actos = bool(d and d.idea_actos and not _misma(d.idea_actos, now) and story.outline)
    return {"preguntas": preguntas, "actos": actos}


def con_idea_leida(story: Story, paso: str) -> Story:
    """La historia con la idea actual guardada como leída en `paso` («preguntas» o
    «actos»). Sin dirección (importada, sin abrir «Tu idea») no se sella: no se le
    inventa una."""
    if story.direction is None:
        return story
    update = {f"idea_{paso}": idea(story)}
    return story.model_copy(update={"direction": story.direction.model_copy(update=update)})


def con_hecho_local(story: Story, respaldos: set[str], *, actos: bool) -> Story:
    """Spec-720 D7: qué hizo la IA de la compu porque la de la nube no atendió (los roles
    de `respaldos`). Armar los actos sella las dos marcas; revisar, solo la de la revisión.
    Sin dirección no se sella (como `con_idea_leida`)."""
    if story.direction is None:
        return story
    update = {"revision_local": "verificador" in respaldos}
    if actos:
        update["actos_locales"] = "planificador" in respaldos
    return story.model_copy(update={"direction": story.direction.model_copy(update=update)})


def hecho_local(story: Story) -> dict[str, bool]:
    """Spec-720 D7: para la nota de «Los actos»."""
    d = story.direction
    return {"actos": bool(d and d.actos_locales), "revision": bool(d and d.revision_local)}


def sin_hecho_local(story: Story) -> Story:
    """Spec-720 D7: «Dejarlo así»."""
    if story.direction is None:
        return story
    update = {"actos_locales": False, "revision_local": False}
    return story.model_copy(update={"direction": story.direction.model_copy(update=update)})


def _oraciones(text: str) -> list[str]:
    return [o.strip() for o in re.split(r"(?<=[.!?…])\s+|\n+", text) if o.strip()]


def lo_que_cambio(antes: str, ahora: str) -> tuple[list[str], list[str]]:
    """Spec-700 S4: las oraciones que se sacaron y las que se agregaron (o cambiaron)."""
    a, b = _oraciones(antes), _oraciones(ahora)
    sacado, agregado = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            sacado += a[i1:i2]
        if op in ("replace", "insert"):
            agregado += b[j1:j2]
    return sacado, agregado


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
        if ending := author_ending(story):  # Spec-690: decidido, venga de donde venga
            fixed = t("asistente/historia/final_decidido")
            lines.append(t("asistente/historia/como_termina", final=ending, decidido=fixed))
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
        c = catalog.criterion(cid, story.structure)
        if c and c.acto:  # Spec-580 D2
            nombre += t("asistente/decisiones/va_en_acto", acto=c.acto)
        if item.status == CriterionStatus.INTENCIONAL:
            rows.append(t("asistente/decisiones/intencional", id=cid, nombre=nombre, texto=texto))
        elif workshop_rules.questions(item):
            rows.append(
                t(
                    "asistente/decisiones/con_pregunta",
                    id=cid,
                    nombre=nombre,
                    pregunta=workshop_rules.questions(item)[-1],
                    texto=texto,
                )
            )
        else:
            rows.append(t("asistente/decisiones/respondida", id=cid, nombre=nombre, texto=texto))
    out = "\n".join(rows) if rows else t("asistente/decisiones/vacio")
    return out + _not_here_block(story, templates)


def _not_here_block(story: Story, templates: TemplateLoader) -> str:
    """Spec-670 D8: lo que no va en esta historia (con su motivo), para que nadie lo pida."""
    t = templates.fragment
    rows = [
        t(
            "asistente/no_va/item",
            id=w.criterion,
            nombre=c.for_story(protagonist(story)).nombre,
            motivo=w.question,
        )
        for w, c in ((w, catalog.criterion(w.criterion)) for w in _direction_items(story))
        if c and w.status == CriterionStatus.NO_APLICA
    ]
    return "\n\n" + t("asistente/no_va/titulo") + "\n" + "\n".join(rows) if rows else ""


def pending_block(story: Story, templates: TemplateLoader) -> str:
    """Preguntas ya hechas que el autor todavía no respondió (no hay que reformularlas)."""
    rows = [
        templates.fragment("asistente/pendientes/pendiente", id=w.criterion, pregunta=w.question)
        for w in _direction_items(story)
        if w.question and not w.answer and w.status != CriterionStatus.INTENCIONAL
    ]
    return "\n".join(rows) if rows else templates.fragment("asistente/pendientes/vacio")


def _direction_items(story: Story) -> list[WorkshopItem]:
    """Spec-670 D11: solo los criterios del molde de la historia. Las respuestas de otra
    forma quedan guardadas (vuelven si se vuelve a esa forma) pero no llegan a la IA."""
    ids = set(molde.for_story(story).ids)
    return [w for w in story.workshop if w.level == WorkshopLevel.DIRECCION and w.criterion in ids]


def effect_recipe(story: Story) -> tuple[str, str]:
    """Spec-560 A5: (nombre del efecto, receta para la escaleta). «Otro» usa el texto del autor."""
    d = story.direction
    if not d or not d.effect:
        return "", ""
    if d.effect == "otro":
        return (d.effect_other, d.effect_other) if d.effect_other.strip() else ("", "")
    option = next((o for o in catalog.effects(story.structure) if o.id == d.effect), None)
    return (option.label, option.planner) if option and option.planner else ("", "")


def effect_block(story: Story, templates: TemplateLoader, verifier: bool = False) -> str:
    name, recipe = effect_recipe(story)
    if not recipe:
        return ""
    role = "verificador" if verifier else "planificador"
    return templates.fragment(f"asistente/efecto/{role}", nombre=name, receta=recipe) + "\n\n"
