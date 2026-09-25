"""Narrar un acto a partir de la escaleta (Spec-530 S5, §8).

La Voz recibe: quién narra y «cómo lo cuenta» (una línea, en vez del perfil del
narrador), la guía de oficio, los hechos del acto, solo los personajes en escena,
el escenario, las reglas del acto, la amenaza según la exposición del acto
(Spec-450), lo que ya pasó (acumulado) y lo ya usado, para no repetirlo.
La memoria (Journal) sale con esquema JSON: hechos, estado y motivos usados.
"""

from pydantic import BaseModel

from src.application.services.authoring import catalog, context, workshop_rules
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.narrative_context_assembler import NarrativeContextAssembler
from src.application.services.prompt_builder import PromptBuilder
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import ActOutline, NarrativeJournal, Story

NUM_ACTS = 5
WORDS_PER_EVENT = 110
MIN_WORDS, MAX_WORDS = 250, 550
LAST_ACT_WORDS = (150, 280)  # desenlace: brevedad emocional
MAX_MOTIFS = 30
_ACT_NAMES = {
    "exposicion": "Exposición",
    "accion_ascendente": "Acción ascendente",
    "climax": "Clímax",
    "accion_descendente": "Acción descendente",
    "desenlace": "Desenlace",
}


class Memoria(BaseModel):
    hechos: str
    estado: str
    motivos_usados: list[str]


def word_range(act: ActOutline) -> tuple[int, int]:
    """Extensión proporcional a los hechos del acto (no 450–530 fijo)."""
    if act.number == NUM_ACTS:
        return LAST_ACT_WORDS
    top = max(MIN_WORDS, min(MAX_WORDS, WORDS_PER_EVENT * max(1, len(act.events)) + 60))
    return max(MIN_WORDS - 50, top - 90), top


def merge_motifs(previous: list[str], new: list[str]) -> list[str]:
    seen, out = set(), []
    for m in [*previous, *new]:
        m = " ".join(str(m).split())
        key = workshop_rules.normalize(m)
        if m and key not in seen:
            seen.add(key)
            out.append(m)
    return out[-MAX_MOTIFS:]


class OutlineNarrator:
    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder | None = None,
        templates: TemplateLoader | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.templates = templates or TemplateLoader()

    # ── Voz ──────────────────────────────────────────────────────────────────

    def voice_prompts(
        self, story: Story, act: ActOutline, memory: NarrativeJournal | None
    ) -> tuple[str, str]:
        narrator = context.narrator(story)
        scene = self._scene_story(story, act, narrator)
        extras = self.prompt_builder._voice_extras(scene)
        telling = story.direction.telling if story.direction else ""
        voice = next((t.voice for t in catalog.tellings() if t.id == telling), "")
        system = self.templates.load("outline_voice_system.md").format(
            presentacion=extras["presentacion"],
            como_lo_cuenta=voice,
            parentescos=extras["parentescos"],
            guia_oficio=extras["guia_oficio"],
        )
        info = self.prompt_builder.get_beat_info(act.number)
        low, high = word_range(act)
        user = self.templates.load("outline_voice.md").format(
            numero=act.number,
            nombre=_ACT_NAMES.get(info.get("name", ""), info.get("name", "")),
            intensidad=info.get("intensity", ""),
            funcion=self._function(story, act, info),
            meta=f"LO QUE QUIERE {_upper(context.protagonist(story))} EN ESTE ACTO: {act.goal}\n"
            if act.goal
            else "",
            narrador=narrator,
            hechos="\n".join(f"- {e}" for e in act.events),
            escenario=self._scenario(story, act),
            en_escena=", ".join(p["name"] for p in scene.personajes_full) or narrator,
            reglas=_section("REGLAS DE ESTE ACTO", story.active_rules_for_beat(act.number)),
            cambio=f"AL TERMINAR EL ACTO: {act.change_to}\n" if act.change_to else "",
            no_revelar=f"NO REVELES TODAVÍA: {act.held_back}\n" if act.held_back else "",
            amenaza=self._threat(story, act),
            ya_paso=(
                memory.last_events
                if memory and memory.last_events
                else "(es el comienzo del relato)"
            )
            + (
                f"\nEstado: {memory.physical_emotional_state}"
                if memory and memory.physical_emotional_state
                else ""
            ),
            ya_usado="\n".join(f"- {m}" for m in memory.used_motifs)
            if memory and memory.used_motifs
            else "(nada todavía)",
            min_palabras=low,
            max_palabras=high,
        )
        return system, user

    def _function(self, story: Story, act: ActOutline, info: dict) -> str:
        d = story.direction
        if act.number == NUM_ACTS and d and d.ending_intentional and d.ending:
            # El final del autor manda sobre la función genérica del acto (Spec-530 S2).
            return f"cerrar la historia con el final que decidió el autor: {d.ending}"
        return info.get("intent", "")

    def _scenario(self, story: Story, act: ActOutline) -> str:
        known = next((s for s in story.scenarios if s.name == act.scenario), None)
        if known and known.description:
            return f"{known.name}: {known.description}"
        return act.scenario or "(no se indica)"

    def _threat(self, story: Story, act: ActOutline) -> str:
        if not story.entities:
            return ""
        assembler = NarrativeContextAssembler(self.prompt_builder._beat_repo)
        act_texts = [" ".join(a.events) for a in story.outline]
        return "\n".join(assembler._amenaza_block(act.number, story.entities, act_texts)) + "\n"

    @staticmethod
    def _scene_story(story: Story, act: ActOutline, narrator: str) -> Story:
        """La historia con solo los personajes en escena (y quien narra): la Voz no ve al resto."""
        on_stage = {workshop_rules.normalize(n) for n in [*act.on_stage, narrator]}
        cast = []
        for p in story.personajes_full or []:
            if workshop_rules.normalize(p.get("name", "")) in on_stage:
                cast.append({**p, "role": p.get("role") or p.get("relation", "")})
        return story.model_copy(update={"personajes_full": cast})

    # ── Memoria ──────────────────────────────────────────────────────────────

    async def remember(
        self, story: Story, act: ActOutline, text: str, previous: NarrativeJournal | None
    ) -> NarrativeJournal:
        prompt = self.templates.load("outline_journal.md").format(
            numero=act.number,
            texto=text,
            memoria=(
                previous.last_events
                if previous and previous.last_events
                else "(nada: es el primer acto)"
            ),
        )
        memoria, _ = await generate_structured(
            self.llm,
            role="journal",
            prompt=prompt,
            system_prompt=self.templates.load("outline_journal_system.md"),
            output=Memoria,
            min_predict=700,
        )
        past = previous.last_events if previous and previous.last_events else ""
        events = f"{past}\nActo {act.number}: {memoria.hechos.strip()}".strip()
        return NarrativeJournal(
            last_events=events,
            physical_emotional_state=memoria.estado.strip(),
            used_motifs=merge_motifs(
                previous.used_motifs if previous else [], memoria.motivos_usados
            ),
        )


def _section(title: str, items: list[str]) -> str:
    return f"{title}:\n" + "\n".join(f"- {i}" for i in items) + "\n" if items else ""


def _upper(name: str) -> str:
    return name.upper() if name else "EL PROTAGONISTA"
