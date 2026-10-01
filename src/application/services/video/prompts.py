"""El prompt del paquete para el video (Spec-610 §3.2), armado con fragmentos (Spec-620).

El relato va con sus párrafos numerados dentro de cada acto, porque la IA responde con
números de párrafo y no con texto. Por acto van el lugar (de la escaleta) y cuánto se
muestra de la amenaza: las imágenes no adelantan lo que todavía no pasó.
"""

from src.application.services.narrative_acts import NarrativeActs
from src.application.services.prompt_builder import PromptBuilder
from src.application.services.template_loader import TemplateLoader
from src.application.services.video import timing
from src.application.services.video.config import VideoConfig
from src.domain.models import Story

SYSTEM_TEMPLATE = "video_script_system.md"
USER_TEMPLATE = "video_script.md"


class VideoScriptPrompts:
    def __init__(self, config: VideoConfig, prompt_builder: PromptBuilder | None = None) -> None:
        self.config = config
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.templates = TemplateLoader(self.prompt_builder.prompts_dir)

    def build(
        self, story: Story, narrative: NarrativeActs, problems: list[str] | None = None
    ) -> tuple[str, str]:
        """(system, user). `problems`: lo que falló en la respuesta anterior (reintento)."""
        fragment = self.templates.fragment
        cfg = self.config
        presentador = cfg.presentador.nombre
        system = self.templates.load(SYSTEM_TEMPLATE).format(presentador=presentador)
        total = sum(len(narrative.paragraphs(n)) for n in narrative.numbers())
        words = sum(timing.palabras(narrative.acts[n]) for n in narrative.numbers())
        ppm = cfg.lectura.palabras_por_minuto
        user = self.templates.load(USER_TEMPLATE).format(
            titulo=story.title,
            relato="\n".join(self._act(n, narrative) for n in narrative.numbers()),
            actos="\n".join(self._context(story, n) for n in narrative.numbers()),
            ppm=ppm,
            duracion=timing.largo(timing.segundos(words, ppm)),
            calabaza=self._presenter(),
            pantalla=fragment(
                "video/pantalla", prohibidas=", ".join(cfg.biblia.palabras_prohibidas)
            ),
            reintento=(
                fragment(
                    "video/reintento",
                    problemas="\n".join(fragment("video/problema", texto=p) for p in problems),
                )
                if problems
                else ""
            ),
            momentos_desde=min(cfg.biblia.momentos.desde, total),
            momentos_hasta=min(cfg.biblia.momentos.hasta, total),
            transiciones=", ".join(cfg.biblia.transiciones),
            presentador=presentador,
        )
        return system, user

    def _act(self, number: int, narrative: NarrativeActs) -> str:
        fragment = self.templates.fragment
        paragraphs = "\n".join(
            fragment("video/parrafo", numero=i, texto=p)
            for i, p in enumerate(narrative.paragraphs(number), start=1)
        )
        label = self.prompt_builder.get_beat_info(number).get("label", "")
        return fragment("video/acto", numero=number, nombre=label, parrafos=paragraphs)

    def _context(self, story: Story, number: int) -> str:
        fragment = self.templates.fragment
        act = next((a for a in story.outline if a.number == number), None)
        place = (act.scenario if act else "") or fragment("video/lugar_vacio")
        threat = ""
        if story.entities:
            main = min(story.entities, key=lambda e: e.order_index)
            exposure = self.prompt_builder._beat_repo.exposure_for(number, main.reveal_level)
            if exposure.get("guide"):
                threat = fragment("video/amenaza", guia=exposure["guide"])
        return fragment("video/acto_contexto", numero=number, lugar=place, amenaza=threat)

    def _presenter(self) -> str:
        fragment = self.templates.fragment
        p = self.config.presentador
        return fragment(
            "video/calabaza",
            presentador=p.nombre.upper(),
            quien_es=p.quien_es,
            como_habla=p.como_habla,
            formato_voz=p.formato_voz,
            intro_desde=p.intro.palabras.desde,
            intro_hasta=p.intro.palabras.hasta,
            intro_guia=p.intro.guia,
            outro_desde=p.outro.palabras.desde,
            outro_hasta=p.outro.palabras.hasta,
            outro_forma="\n".join(
                fragment("video/paso", numero=i, paso=paso)
                for i, paso in enumerate(p.outro.forma, start=1)
            ),
            cierra_con=p.outro.cierra_con,
            ejemplos="\n".join(fragment("video/ejemplo", texto=e) for e in p.ejemplos_outro),
        )
