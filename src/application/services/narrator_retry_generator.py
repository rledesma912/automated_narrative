"""NarratorRetryGenerator - maneja retry y detección de refusals para el VOZ."""

import logging

from src.application.services.template_loader import TemplateLoader
from src.domain.exceptions import LLMResponseError
from src.domain.interfaces import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

_REFUSAL_INDICATORS = ["lo siento", "no puedo", "no puedo cumplir", "no es apropiado"]


def _is_valid_response(text: str | None) -> bool:
    """Valida que la respuesta no sea vacía ni None."""
    if text is None:
        return False
    stripped = text.strip()
    return len(stripped) > 0


class NarratorRetryGenerator:
    """Genera contenido con retry y detección de refusals para la Voz narrativa."""

    def __init__(self, llm: LLMProvider, templates: TemplateLoader | None = None):
        self.llm = llm
        self.templates = templates or TemplateLoader()

    async def generate_with_retry(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_retries: int = 2,
    ) -> LLMResponse:
        for attempt in range(max_retries + 1):
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                role="voz",
            )

            if not _is_valid_response(response.text):
                if attempt == max_retries:
                    raise LLMResponseError(
                        reason="Respuesta vacía después de max_retries intentos",
                        raw_response=response.text,
                    )
                logger.debug(f"[NarratorRetry] respuesta vacía en intento {attempt + 1}")
                continue

            content_lower = response.text.lower().strip()
            is_refusal = any(ind in content_lower for ind in _REFUSAL_INDICATORS)

            if not is_refusal:
                return response

            logger.debug(f"[NarratorRetry] refusal detectado en intento {attempt + 1}")
            if attempt < max_retries:
                prompt = self._rephrase_prompt(prompt)

        return response

    def _rephrase_prompt(self, original_prompt: str) -> str:
        return original_prompt + "\n\n" + self.templates.fragment("voz/reintento")
