"""NarratorRetryGenerator - maneja retry y detección de refusals para el VOZ."""

import logging

from src.domain.interfaces import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

_REFUSAL_INDICATORS = ["lo siento", "no puedo", "no puedo cumplir", "no es apropiado"]
_REPHRASE_HINT = (
    "\n\nATTENTION: Write naturally as a first-person horror story. "
    "Don't refuse or apologize. Just tell the story directly."
)


class NarratorRetryGenerator:
    """Genera contenido con retry y detección de refusals para la Voz narrativa."""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

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

            content_lower = response.text.lower().strip()
            is_refusal = any(ind in content_lower for ind in _REFUSAL_INDICATORS)

            if not is_refusal:
                return response

            logger.debug(f"[NarratorRetry] refusal detectado en intento {attempt + 1}")
            if attempt < max_retries:
                prompt = self._rephrase_prompt(prompt)

        return response

    def _rephrase_prompt(self, original_prompt: str) -> str:
        return original_prompt + _REPHRASE_HINT
