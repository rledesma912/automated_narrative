"""PromptBuilder - piezas compartidas de los prompts (Spec-530 S7).

Tras retirar el pipeline viejo quedan: la definición de los 5 actos
(`llm_beats_definition.yaml`) y los extras de la Voz de la Spec-470 (guía de
oficio, parentescos y presentación de quien narra). Los prompts en sí los arman
los servicios del asistente (`authoring/`).
"""

import logging
from pathlib import Path

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.template_loader import TemplateLoader
from src.application.services.voice_cliches import load_cliches
from src.config import settings
from src.domain.models import Story

logger = logging.getLogger(__name__)

VOICE_CRAFT_FILE = "voice_craft.md"  # Spec-470: guía de oficio de la Voz


class PromptBuilder:
    def __init__(self, prompts_dir: str | None = None):
        self.prompts_dir = Path(prompts_dir or settings.prompts_dir)
        self._loader = TemplateLoader(self.prompts_dir)
        self._beat_repo = BeatSpecRepository()
        self.num_beats: int = self._beat_repo.num_beats

    def get_beat_info(self, beat_id: int, reveal_level: str | None = None) -> dict:
        """Nombre, intención e intensidad del acto (y reglas de revelación, Spec-450)."""
        return self._beat_repo.get_by_id(beat_id, reveal_level)

    # -- Spec-470: oficio de la Voz ----------------------------------------------

    def narrator_name(self, story: Story) -> str:
        """Nombre de quien narra: `storyteller_name` o el personaje de `storyteller_id`."""
        config = story.narrator_config or {}
        if config.get("storyteller_name"):
            return config["storyteller_name"]
        pid = config.get("storyteller_id")
        person = next((p for p in story.personajes_full if pid and p.get("id") == pid), None)
        return (person or {}).get("name", "")

    def _voice_extras(self, story: Story) -> dict[str, str]:
        """Guía de oficio, parentescos y presentación para el system prompt de la Voz."""
        narrator = self.narrator_name(story)
        cliches = "\n".join(f"  - «{c}»" for c in load_cliches())
        craft = self._loader.load(VOICE_CRAFT_FILE) or ""
        return {
            "guia_oficio": craft.format(
                cliches=cliches, narrador=narrator or "el narrador"
            ).strip(),
            "parentescos": self._format_kinship(story, narrator),
            # «Sos Irene…» en vez de «Sos Primera persona en pasado. Narrador: Irene…».
            "presentacion": (
                f"Sos {narrator} y contás en primera persona los hechos de la historia "
                f"({story.relator})."
                if narrator
                else f"Sos {story.relator}, narrando en primera persona los hechos de la historia."
            ),
        }

    @staticmethod
    def _format_kinship(story: Story, narrator: str) -> str:
        """«CÓMO LLAMÁS A CADA PERSONAJE»: el rol de cada uno, leído desde quien narra.

        Va pegado al elenco en el template: vacío no deja líneas en blanco; con contenido
        arranca con una línea de separación.
        """
        others = [p for p in story.personajes_full if p.get("name") and p["name"] != narrator]
        if not narrator or not others:
            return ""
        lines = [
            "",
            "",
            f"CÓMO LLAMÁS A CADA PERSONAJE (sos {narrator}):",
            "Cuando nombres a alguien por su parentesco, usá la relación que tiene CON VOS según "
            f"su rol; nunca otra. Si un rol dice «Suegra de {narrator}», es tu suegra: no tu madre "
            "ni tu abuela.",
        ]
        lines += [f"- {p['name']}: {p.get('role') or 'sin rol'}" for p in others]
        return "\n".join(lines)
