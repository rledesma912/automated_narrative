"""Narrar un acto a partir de la escaleta (Spec-530 S5, §8).

La Voz recibe: quién narra y «cómo lo cuenta» (una línea, en vez del perfil del
narrador), la guía de oficio, la premisa (Spec-590), los hechos del acto, solo los
personajes en escena, el escenario, las reglas del acto, la amenaza según la
exposición del acto (Spec-450), lo que ya pasó (los eventos de la escaleta de los
actos anteriores, Spec-590 E), cómo está y cómo es quien narra (de la memoria) y lo
ya usado, para no repetirlo.
La memoria (Journal) sale con esquema JSON: hechos, estado, cuerpo, rasgos de quien
narra y motivos usados.

Spec-620: el texto de cada sección vive en `config/prompts_generation/fragments/voz/` y
`fragments/memoria/`; este módulo decide qué secciones van y con qué datos.
"""

import re

from pydantic import BaseModel

from src.application.services.authoring import catalog, context, workshop_rules
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.manifestations import manifestations_for_act
from src.application.services.prompt_builder import PromptBuilder
from src.application.services.structure import DEFAULT_STRUCTURE, Estructura
from src.application.services.template_loader import TemplateLoader
from src.domain.interfaces import LLMProvider
from src.domain.models import ActOutline, NarrativeJournal, Story

# Spec-610 D11 (en la Spec-600 S1): un episodio de ~15 min leído en voz alta, ≈ 1 950
# palabras a 130 por minuto. Antes (Spec-590 D) 170 / 400–900 / 250–450 daban ~3 200.
WORDS_PER_EVENT = 100
MIN_WORDS, MAX_WORDS = 250, 500
RANGE_WIDTH = 100
LAST_ACT_WORDS = (180, 300)  # desenlace: más corto que el resto
MAX_MOTIFS = 30
MAX_TRAITS = 12  # Spec-590 C: rasgos de quien narra que se sostienen entre actos
ENDING_WORDS = 120  # Spec-590: tope del último párrafo del acto anterior


class Memoria(BaseModel):
    hechos: str
    estado: str
    cuerpo: str
    asi_es: list[str]
    motivos_usados: list[str]


def word_range(act: ActOutline, estructura: Estructura | None = None) -> tuple[int, int]:
    """Extensión proporcional a los hechos del acto (no 450–530 fijo).

    Spec-650: si la estructura fija `palabras` para el acto, manda ese rango.
    """
    estructura = estructura or BeatSpecRepository().estructura()
    fixed = estructura.acto(act.number).get("palabras")
    if fixed:
        return fixed[0], fixed[1]
    if act.number == estructura.ultimo:
        return LAST_ACT_WORDS
    top = max(MIN_WORDS, min(MAX_WORDS, WORDS_PER_EVENT * max(1, len(act.events)) + 60))
    return max(MIN_WORDS - 50, top - RANGE_WIDTH), top


def merge_motifs(previous: list[str], new: list[str], limit: int = MAX_MOTIFS) -> list[str]:
    seen, out = set(), []
    for m in [*previous, *new]:
        m = " ".join(str(m).split())
        key = workshop_rules.normalize(m)
        if m and key not in seen:
            seen.add(key)
            out.append(m)
    return out[-limit:]


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
        self,
        story: Story,
        act: ActOutline,
        memory: NarrativeJournal | None,
        previous_text: str = "",
        avoid=None,
    ) -> tuple[str, str]:
        """`avoid`: lo que el control marcó en la versión anterior de este acto (A2/A6)."""
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
        estructura = self.prompt_builder.estructura(story)
        info = self.prompt_builder.get_beat_info(act.number, structure=estructura.id)
        low, high = word_range(act, estructura)
        user = self.templates.load("outline_voice.md").format(
            numero=act.number,
            historia=self._premise(story, narrator),
            puente=self._bridge(act),
            evitar=self._avoid(avoid),
            final_anterior=self._ending_of(previous_text),
            nombre=info.get("label") or info.get("name", ""),
            intensidad=info.get("intensity", ""),
            funcion=self._function(story, act, info),
            meta=self._line(
                "voz/objetivo",
                protagonista=self._upper(context.protagonist(story)),
                objetivo=act.goal,
            )
            if act.goal
            else "",
            narrador=narrator,
            hechos="\n".join(f"- {e}" for e in act.events),
            escenario=self._scenario(story, act),
            en_escena=", ".join(p["name"] for p in scene.personajes_full) or narrator,
            reglas=_section(
                self.templates.fragment("voz/reglas"), story.active_rules_for_beat(act.number)
            ),
            cambio=self._line("voz/cambio", cambio=act.change_to) if act.change_to else "",
            no_revelar=self._line("voz/no_revelar", secreto=act.held_back) if act.held_back else "",
            amenaza=self._threat(story, act),
            ya_paso=self._already_happened(story, act, memory),
            como_esta=self._how_is(memory, narrator),
            asi_es=_section(
                self.templates.fragment("voz/asi_es", narrador=self._upper(narrator)),
                memory.narrator_traits if memory else [],
            ),
            ya_usado="\n".join(f"- {m}" for m in self._motifs_for(story, act, memory))
            or self.templates.fragment("voz/ya_usado_vacio"),
            min_palabras=low,
            max_palabras=high,
        )
        return system, user

    def _line(self, name: str, **data: object) -> str:
        """Un fragmento que ocupa su propia línea en el prompt."""
        return self.templates.fragment(name, **data) + "\n"

    def _upper(self, name: str) -> str:
        return name.upper() if name else self.templates.fragment("voz/protagonista")

    def _function(self, story: Story, act: ActOutline, info: dict) -> str:
        d = story.direction
        last = self.prompt_builder.estructura(story).ultimo
        if act.number == last and d and d.ending_intentional and d.ending:
            # El final del autor manda sobre la función genérica del acto (Spec-530 S2).
            return self.templates.fragment("voz/final_del_autor", final=d.ending)
        return info.get("intent", "")

    @staticmethod
    def _motifs_for(story: Story, act: ActOutline, memory: NarrativeJournal | None) -> list[str]:
        """Spec-590: «ya usado» sin lo que este acto tiene que mostrar.

        Un motivo cuyas palabras están todas en los EVENTOS del acto o en la ficha de la
        amenaza («ojos brillantes», «susurros») no se prohíbe: es lo que se pide contar.
        """
        if not memory:
            return []
        texts = [
            *act.events,
            *(f"{e.name} {e.description} {e.manifestations}" for e in story.entities),
        ]
        allowed = {w for w in workshop_rules.normalize(" ".join(texts)).split() if len(w) > 3}

        def required(motif: str) -> bool:
            words = [w for w in workshop_rules.normalize(motif).split() if len(w) > 3]
            return bool(words) and all(w in allowed for w in words)

        return [m for m in memory.used_motifs if not required(m)]

    def _scenario(self, story: Story, act: ActOutline) -> str:
        known = next((s for s in story.scenarios if s.name == act.scenario), None)
        if known and known.description:
            return f"{known.name}: {known.description}"
        return act.scenario or self.templates.fragment("voz/escenario_vacio")

    def _threat(self, story: Story, act: ActOutline) -> str:
        if not story.entities:
            return ""
        act_texts = [" ".join(a.events) for a in story.outline]
        lines = self._threat_lines(act.number, story.entities, act_texts, story.structure)
        return "\n".join(lines) + "\n"

    def _threat_lines(
        self,
        beat_number: int,
        entities,
        act_texts: list[str],
        structure: str = DEFAULT_STRUCTURE,
    ) -> list[str]:
        """Solo los campos que la exposición del acto permite ver de cada entidad (Spec-450).

        Con «señales» la Voz no recibe ni el nombre ni la naturaleza: no puede revelarlos.
        """
        lines = [self.templates.fragment("voz/amenaza/titulo")]
        beat_repo = self.prompt_builder._beat_repo
        for e in entities:
            exposure = beat_repo.exposure_for(beat_number, e.reveal_level, structure)
            show = exposure.get("show", ["manifestations"])
            head = []
            if "name" in show and e.name:
                head.append(e.name)
            if "nature" in show:
                head.append(e.nature_label or e.nature_id)
            presence = self.templates.fragment("voz/amenaza/presencia", numero=e.order_index + 1)
            lines.append(f"- {' — '.join(head) if head else presence}")
            for key, fragment in (
                ("description", "voz/amenaza/que_es"),
                ("manifestations", "voz/amenaza/como_se_percibe"),
                ("limits", "voz/amenaza/limites"),
            ):
                value = getattr(e, key)
                if key == "manifestations" and exposure.get("max_manifestations") and act_texts:
                    value = "; ".join(
                        manifestations_for_act(
                            value, beat_number, act_texts, exposure["max_manifestations"]
                        )
                    )
                if key in show and value:
                    lines.append(self.templates.fragment(fragment, valor=value))
            if exposure.get("guide"):
                lines.append(
                    self.templates.fragment("voz/amenaza/como_mostrarla", valor=exposure["guide"])
                )
        return lines

    @staticmethod
    def _scene_story(story: Story, act: ActOutline, narrator: str) -> Story:
        """La historia con los personajes de este acto: los que están en escena, quien narra
        y los que los eventos nombran (así la Voz sabe cómo llamarlos: «mi suegra»).

        La Voz no ve al resto del elenco.
        """
        on_stage = {workshop_rules.normalize(n.split("(")[0]) for n in [*act.on_stage, narrator]}
        events = workshop_rules.normalize(" ".join([act.goal, *act.events]))
        cast = []
        for p in story.personajes_full or []:
            name = workshop_rules.normalize(p.get("name", ""))
            if name and (name in on_stage or re.search(rf"\b{re.escape(name)}\b", events)):
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
                else self.templates.fragment("memoria/memoria_vacia")
            ),
            cuerpo=(
                previous.body_state
                if previous and previous.body_state
                else self.templates.fragment("memoria/cuerpo_vacio")
            ),
            asi_es="\n".join(f"- {t}" for t in previous.narrator_traits)
            if previous and previous.narrator_traits
            else self.templates.fragment("memoria/asi_es_vacio"),
        )
        memoria, _ = await generate_structured(
            self.llm,
            role="journal",
            prompt=prompt,
            system_prompt=self.templates.load("outline_journal_system.md"),
            output=Memoria,
            min_predict=900,
        )
        past = previous.last_events if previous and previous.last_events else ""
        this_act = self.templates.fragment(
            "memoria/hechos_acto", numero=act.number, hechos=memoria.hechos.strip()
        )
        events = f"{past}\n{this_act}".strip()
        return NarrativeJournal(
            last_events=events,
            physical_emotional_state=memoria.estado.strip(),
            used_motifs=merge_motifs(
                previous.used_motifs if previous else [], memoria.motivos_usados
            ),
            body_state=memoria.cuerpo.strip(),
            narrator_traits=merge_motifs(
                previous.narrator_traits if previous else [], memoria.asi_es, MAX_TRAITS
            ),
        )

    # ── Secciones del prompt de la Voz ───────────────────────────────────────

    def _avoid(self, rep) -> str:
        """Spec-560 A2/A6: lo que la versión anterior de este acto repitió o inventó."""
        if rep is None:
            return ""
        t = self.templates
        lines = [t.fragment("voz/evitar/repetida", frase=f, acto=a) for f, a in rep.repeated]
        lines += [t.fragment("voz/evitar/cliche", cliche=c) for c in rep.cliches]
        if rep.invented_names:
            lines.append(t.fragment("voz/evitar/nombres", nombres=", ".join(rep.invented_names)))
        if rep.too_cut:
            ejemplos = ", ".join(f"«{s}»" for s in rep.cut_sentences)
            lines.append(
                t.fragment("voz/evitar/cortadas", cantidad=rep.cut_count, ejemplos=ejemplos)
            )
        if rep.dialogue:
            lines.append(t.fragment("voz/evitar/dialogo"))
        if rep.too_literary:  # Spec-640
            ejemplos = ", ".join(f"«{s}»" for s in rep.comparisons)
            lines.append(
                t.fragment(
                    "voz/evitar/comparaciones", cantidad=rep.comparison_count, ejemplos=ejemplos
                )
            )
        if not lines:
            return ""
        return t.fragment("voz/evitar/titulo") + "\n" + "\n".join(lines) + "\n\n"

    def _bridge(self, act: ActOutline) -> str:
        """Spec-560 A1: cómo se llega al acto (tiempo y camino), para abrirlo sin saltos."""
        if act.number == 1 or not act.bridge.strip():
            return ""
        return self._line("voz/puente", puente=act.bridge.strip())

    def _ending_of(self, previous_text: str) -> str:
        """Spec-560 A1 / Spec-590: el último párrafo del acto anterior, textual, para seguir
        desde ahí (hasta 120 palabras: si es más largo, sus últimas oraciones)."""
        paragraphs = [p for p in re.split(r"\n\s*\n", previous_text.strip()) if p.strip()]
        if not paragraphs:
            return ""
        parts = re.split(r"(?<=[.!?…»])\s+", " ".join(paragraphs[-1].split()))
        tail: list[str] = []
        for sentence in reversed(parts):
            if tail and len(" ".join([sentence, *tail]).split()) > ENDING_WORDS:
                break
            tail.insert(0, sentence)
        tail = " ".join(tail).strip()
        if not tail:
            return ""
        return self._line("voz/final_anterior", final=tail)

    def _premise(self, story: Story, narrator: str) -> str:
        """Spec-590: la idea de quien escribe, para que la Voz conozca a quien narra y su
        mundo. Solo la primera oración: el resto de la premisa adelantaba hechos de actos
        posteriores."""
        d = story.direction
        premise = " ".join(((d.premise if d and d.premise else "") or story.sinopsis or "").split())
        premise = _SENTENCE_END.split(premise, maxsplit=1)[0]
        if not premise:
            return ""
        return self._line("voz/historia", narrador=self._upper(narrator), premisa=premise)

    def _already_happened(
        self, story: Story, act: ActOutline, memory: NarrativeJournal | None
    ) -> str:
        """Spec-590 E: los EVENTOS de la escaleta de los actos anteriores (confirmados por
        quien escribe), no el resumen de la memoria. Sin escaleta, cae a la memoria."""
        previous = [
            a for a in sorted(story.outline, key=lambda a: a.number) if a.number < act.number
        ]
        lines = [
            self.templates.fragment("voz/ya_paso_acto", numero=a.number, hechos=" ".join(a.events))
            for a in previous
            if a.events
        ]
        if lines:
            return "\n".join(lines)
        if memory and memory.last_events:
            return memory.last_events
        return self.templates.fragment("voz/ya_paso_vacio")

    def _how_is(self, memory: NarrativeJournal | None, narrator: str) -> str:
        """Spec-590 E: dónde y cómo quedó quien narra, y su cuerpo (heridas con el lugar)."""
        parts = (
            [p.strip() for p in (memory.physical_emotional_state, memory.body_state) if p.strip()]
            if memory
            else []
        )
        if not parts:
            return ""
        return self._line("voz/como_esta", narrador=self._upper(narrator), estado=" ".join(parts))


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[¿¡«\"“(]?[A-ZÁÉÍÓÚÑ])")


def _section(title: str, items: list[str]) -> str:
    return f"{title}:\n" + "\n".join(f"- {i}" for i in items) + "\n" if items else ""
