"""Contexto de la historia que reciben los roles del asistente (Spec-530).

Lleva el objetivo y la dirección del autor (sin eso las preguntas no se atan a lo
que quiere contar), no la teoría: los criterios ya vienen como preguntas concretas.
"""

from src.application.services.authoring import catalog
from src.domain.models import CriterionStatus, Story, WorkshopItem, WorkshopLevel

OBJETIVO = (
    "Estamos ayudando a un autor a preparar un cuento de terror que después se "
    "genera automáticamente en 5 actos (unas 2.500 palabras) y se escucha como audio."
)


def protagonist(story: Story) -> str:
    cast = story.personajes_full or []
    return cast[0].get("name", "") if cast else story.protagonista.split(":")[0].strip()


def narrator(story: Story) -> str:
    cfg = story.narrator_config or {}
    return cfg.get("storyteller_name") or protagonist(story)


def story_block(story: Story) -> str:
    """Qué historia es y qué quiere el autor."""
    d = story.direction
    lines = [f"Título: {story.title}"]
    genre = " / ".join(x for x in (story.genero, story.subgenero) if x)
    if genre:
        lines.append(f"Tipo de horror: {genre}")
    lines.append(f"De qué trata: {(d.premise if d and d.premise else story.sinopsis).strip()}")
    lines.append(f"Protagonista: {story.protagonista}")
    lines.append(f"Quién lo cuenta: {narrator(story)}")
    if d:
        if d.effect:
            effect = (
                d.effect_other
                if d.effect == "otro"
                else catalog.label_of(catalog.effects(), d.effect)
            )
            lines.append(f"Efecto que busca el autor: {effect}")
        if d.telling:
            lines.append(f"Cómo lo cuenta: {catalog.label_of(catalog.tellings(), d.telling)}")
        if d.ending:
            fixed = (
                " (DECIDIDO POR EL AUTOR: no se discute ni se cambia)"
                if d.ending_intentional
                else ""
            )
            lines.append(f"Cómo termina: {d.ending}{fixed}")
    cast = [p for p in story.personajes_full or [] if p.get("name")]
    if len(cast) > 1:
        lines.append("Personajes: " + "; ".join(_person(p) for p in cast))
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
            out.append((c.id, c.nombre, item.answer))
    return out


def decisions_block(story: Story) -> str:
    """Historial del taller como pregunta → respuesta: sin la pregunta, una respuesta
    corta («su hija») no se entiende."""
    by_id = {w.criterion: w for w in _direction_items(story)}
    rows = []
    for cid, nombre, texto in decisions(story):
        item = by_id[cid]
        if item.status == CriterionStatus.INTENCIONAL:
            rows.append(f"- [{cid}] {nombre}: {texto} (DECIDIDO POR EL AUTOR: no se discute)")
        elif item.asked:
            rows.append(f"- [{cid}] {nombre}. Pregunta: «{item.asked[-1]}» → Respuesta: {texto}")
        else:
            rows.append(f"- [{cid}] {nombre}: {texto}")
    if not rows:
        return "(el autor todavía no tomó decisiones en el taller)"
    return "\n".join(rows)


def pending_block(story: Story) -> str:
    """Preguntas ya hechas que el autor todavía no respondió (no hay que reformularlas)."""
    rows = [
        f"- [{w.criterion}] «{w.question}»"
        for w in _direction_items(story)
        if w.question and not w.answer and w.status != CriterionStatus.INTENCIONAL
    ]
    return "\n".join(rows) if rows else "(ninguna)"


def _direction_items(story: Story) -> list[WorkshopItem]:
    return [w for w in story.workshop if w.level == WorkshopLevel.DIRECCION]
