"""Envoltorio que anota cada llamada a la IA de un job (Spec-740 B3).

Lo arma `LLMFactory.get_provider()` alrededor de cualquier adapter: así ningún caso de
uso cambia. Fuera de un job (CLI, scripts, tests sin contexto) solo delega. Si anotar
falla, el relato no se pierde: se loguea y la llamada sigue (B4).
"""

import logging

from src.config import settings
from src.domain import llm_context
from src.domain.interfaces import LLMProvider, LLMResponse
from src.domain.llm_context import LLMCall

logger = logging.getLogger(__name__)


class RegistroLLM:
    def __init__(self, inner: LLMProvider, repo=None) -> None:
        self._inner = inner
        self._repo = repo

    def __getattr__(self, name: str):
        # `respaldos`, `adapter_for`… los sigue viendo quien los usa (Spec-720 D7).
        return getattr(self._inner, name)

    @property
    def inner(self) -> LLMProvider:
        return self._inner

    async def generate(self, prompt: str, *args, role: str | None = None, **kwargs) -> LLMResponse:
        response = await self._inner.generate(prompt, *args, role=role, **kwargs)
        context = llm_context.current()
        if context is not None:
            await self._anotar(context, role, response)
        return response

    async def _anotar(self, context, role: str | None, response: LLMResponse) -> None:
        try:
            repo = self._repo
            if repo is None:
                from src.infrastructure.database.repositories import SQLLLMCallRepository

                repo = self._repo = SQLLLMCallRepository()
            await repo.add(
                LLMCall(
                    story_id=context.story_id,
                    job_id=context.job_id,
                    role=role,
                    act=context.act,
                    profile=settings.active_profile_name,
                    provider=getattr(response, "provider", None),
                    model=getattr(response, "model", None),
                    via=getattr(response, "via", None),
                    fallback_attempts=getattr(response, "fallback_attempts", 0) or 0,
                    fallback_trail=getattr(response, "fallback_trail", None),
                    respaldo=bool(getattr(response, "respaldo", False)),
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    elapsed_s=response.elapsed_s,
                )
            )
        except Exception:  # noqa: BLE001 — B4: el registro nunca corta el job
            logger.exception("[REGISTRO] No se pudo anotar la llamada de %s", role)

    async def close(self) -> None:
        await self._inner.close()
