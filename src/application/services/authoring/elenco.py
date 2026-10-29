"""Spec-700 B: los personajes que nombró la autora no se preguntan, se suman solos.

Sin IA. Un nombre de «Quiénes están» es de la autora si aparece en lo que ella
escribió (`author_text` de la Spec-680: la idea, quién narra, sus respuestas, sus
reglas…) o si es «<algo> de <quien narra>» y ese algo aparece («Mamá de Ximena»
con «la tienda de su mamá»). Lo demás lo inventó la IA y sigue avisándose.
"""

import re
from difflib import SequenceMatcher

from src.application.services import recursos_gastados
from src.application.services.authoring import context, workshop_rules
from src.domain.models import ActOutline, Story

PARECIDO = 0.8  # «Amigos» / «Amigas» (0,83) sí; «Amigas» / «Mamá» (de Ximena) no


def bare(name: str) -> str:
    """«María (aparición)» es María: sin agregados entre paréntesis."""
    return " ".join(name.split("(")[0].split())


def _in(words: str, text: str) -> bool:
    return bool(words) and re.search(rf"\b{re.escape(words)}\b", text) is not None


def clave(name: str) -> str:
    """La clave del aviso de personajes de este nombre (Spec-550 H10: estable)."""
    return f"elenco:{workshop_rules.normalize(bare(name))}"


def sin_aviso(act: ActOutline, name: str) -> ActOutline:
    """B3: el acto sin el aviso de personajes de este nombre (resuelto, no ignorado)."""
    key = clave(name)
    return act.model_copy(update={"warnings": [w for w in act.warnings if w.key != key]})


def _ratio(a: str, b: str) -> float:
    """Letra por letra; con el mismo «de <alguien>» al final se compara solo lo de adelante
    («Amigas de Ximena» no se parece a «Mamá de Ximena» por compartir «de Ximena»)."""
    ha, sa, oa = a.partition(" de ")
    hb, sb, ob = b.partition(" de ")
    if sa and sb and oa == ob:
        a, b = ha, hb
    return SequenceMatcher(None, a, b).ratio()


def parecido(name: str, cast: list[str]) -> str:
    """B4: el nombre de la lista que se le parece, o vacío (el mismo nombre no cuenta)."""
    key = workshop_rules.normalize(bare(name))
    best, score = "", PARECIDO
    for other in cast:
        other_key = workshop_rules.normalize(bare(other))
        if other_key == key:
            return ""
        ratio = _ratio(key, other_key)
        if ratio >= score:
            best, score = other, ratio
    return best


def de_la_autora(story: Story, name: str, text: str | None = None) -> bool:
    """D20: ¿este nombre sale de lo que escribió la autora?"""
    text = workshop_rules.normalize(recursos_gastados.author_text(story) if text is None else text)
    key = workshop_rules.normalize(bare(name))
    if _in(key, text):
        return True
    narrator = workshop_rules.normalize(context.narrator(story))
    head, sep, owner = key.partition(" de ")
    return bool(sep) and owner == narrator and _in(head, text)


def personajes_de_la_autora(story: Story, acts: list[ActOutline]) -> list[str]:
    """D22: los nombres de «Quiénes están» que son de la autora y todavía no están entre
    los personajes (ni son quien narra ni la amenaza), en orden de aparición."""
    known = {workshop_rules.normalize(p.get("name", "")) for p in story.personajes_full or []}
    known.add(workshop_rules.normalize(context.narrator(story)))
    known |= {workshop_rules.normalize(e.name) for e in story.entities if e.name}
    text = recursos_gastados.author_text(story)
    out: list[str] = []
    for act in sorted(acts, key=lambda a: a.number):
        for raw in act.on_stage:
            name = bare(raw)
            key = workshop_rules.normalize(name)
            if key and key not in known and de_la_autora(story, name, text):
                known.add(key)
                out.append(name)
    return out


def next_id(cast: list[dict]) -> str:
    """P<n> que no choque con ninguno (al borrar un personaje, `len + 1` repetiría un id)."""
    nums = [
        int(p["id"][1:])
        for p in cast
        if str(p.get("id", "")).startswith("P") and p["id"][1:].isdigit()
    ]
    return f"P{max(nums, default=0) + 1}"


def con_personajes(story: Story, names: list[str]) -> Story:
    """La historia con esos personajes sumados (persona, sin parentesco: D21)."""
    if not names:
        return story
    cast = list(story.personajes_full or [])
    for name in names:
        cast.append(
            {"id": next_id(cast), "name": name, "role": "", "kind": "persona", "relation": ""}
        )
    return story.model_copy(update={"personajes_full": cast})
