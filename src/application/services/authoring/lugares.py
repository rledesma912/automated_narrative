"""Spec-710 D10: los lugares que nombra el Planificador en los hechos son lugares de la
historia (opciones en todos los actos; la Voz recibe su descripción si la tienen).

Sin IA. Antes quedaban sueltos en cada acto (58 de 58 en prod, §1.2).
"""

from src.application.services.authoring import workshop_rules
from src.domain.models import ActOutline, Scenario, Story


def _key(name: str) -> str:
    return workshop_rules.normalize(" ".join(name.split("(")[0].split()))


def nuevos(story: Story, acts: list[ActOutline]) -> list[str]:
    """Los lugares de los actos que la historia todavía no tiene, en orden y sin repetir."""
    known = {_key(s.name) for s in story.scenarios}
    out: list[str] = []
    for act in sorted(acts, key=lambda a: a.number):
        for place in act.places():
            if (key := _key(place)) and key not in known:
                known.add(key)
                out.append(place)
    return out


def con_lugares(story: Story, names: list[str]) -> Story:
    """La historia con esos lugares sumados al final."""
    if not names:
        return story
    start = len(story.scenarios)
    added = [
        Scenario(story_id=story.id, order_index=start + i, name=name)
        for i, name in enumerate(names)
    ]
    return story.model_copy(update={"scenarios": [*story.scenarios, *added]})
