"""Armar el paquete para el video (Spec-610 §3.2): una llamada a la IA (rol `guion`),
los chequeos sin IA y, si algo no cumple, un reintento con la lista de problemas."""

import logging

from src.application.services import narrative_acts
from src.application.services.authoring.structured_llm import generate_structured
from src.application.services.video.config import VideoConfig, video_config
from src.application.services.video.prompts import VideoScriptPrompts
from src.application.services.video.schema import PaqueteIA
from src.application.services.video.script_builder import VideoScriptBuilder
from src.domain.interfaces import LLMProvider
from src.domain.models import GeneratedNarrative, Story
from src.domain.video import VideoScript
from src.messages import message

logger = logging.getLogger(__name__)

ROLE = "guion"


class VideoScriptError(ValueError):
    """La IA no armó un paquete que pase los chequeos (el mensaje va a la pantalla)."""


class VideoScriptService:
    def __init__(self, llm: LLMProvider, config: VideoConfig | None = None) -> None:
        self.llm = llm
        self.config = config or video_config()
        self.prompts = VideoScriptPrompts(self.config)
        self.builder = VideoScriptBuilder(self.config, self.prompts.templates)

    async def generate(self, story: Story, narrative: GeneratedNarrative) -> VideoScript:
        acts = narrative_acts.split(narrative.content)
        if not acts.acts:
            raise VideoScriptError(message("video.relato_sin_actos"))
        problems: list[str] = []
        for attempt in (1, 2):
            system, user = self.prompts.build(story, acts, problems)
            paquete, elapsed = await generate_structured(
                self.llm, role=ROLE, prompt=user, system_prompt=system, output=PaqueteIA
            )
            problems = self.builder.check(paquete, acts)
            logger.info(
                "[VIDEO] intento %d: %d problemas en %.1f s", attempt, len(problems), elapsed
            )
            if not problems:
                return self.builder.build(paquete, acts, narrative.id, narrative.content)
            logger.warning("[VIDEO] problemas: %s", problems)
        raise VideoScriptError(message("video.no_se_pudo_armar", cantidad=len(problems)))
