"""Adapter que despacha cada llamada al proveedor de su rol (Spec-480).

Permite perfiles mixtos: por ejemplo, la Voz en Anthropic y el resto en Ollama.
Todas las llamadas del pipeline pasan `role`, así que el ruteo es por rol.

Spec-720 D6: un rol con `respaldo` (otro proveedor y su config) repite la llamada ahí si
su proveedor no atiende (`LLMUnavailableError`), y queda anotado en `respaldos` para que
el job lo diga en pantalla.
"""

import logging

from src.domain.exceptions import LLMUnavailableError
from src.domain.interfaces import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Lo que el respaldo pisa de la llamada (el resto, como el esquema o el prompt, sigue).
_DEL_RESPALDO = ("model", "temperature", "num_ctx", "num_predict")


class RoleRoutingAdapter:
    """`LLMProvider` compuesto: un adapter por rol y uno por defecto."""

    def __init__(
        self,
        by_role: dict[str, LLMProvider],
        default: LLMProvider,
        respaldo: dict[str, tuple[LLMProvider, dict]] | None = None,
    ) -> None:
        self._by_role = dict(by_role)
        self._default = default
        self._respaldo = dict(respaldo or {})
        self.respaldos: set[str] = set()  # los roles que respondió el respaldo

    def adapter_for(self, role: str | None) -> LLMProvider:
        """Adapter del rol; sin rol o con un rol desconocido, el por defecto."""
        return self._by_role.get(role or "", self._default)

    async def generate(self, prompt: str, *, role: str | None = None, **kwargs) -> LLMResponse:
        try:
            return await self.adapter_for(role).generate(prompt, role=role, **kwargs)
        except LLMUnavailableError as e:
            if (role or "") not in self._respaldo:
                raise
            adapter, cfg = self._respaldo[role]
            logger.warning(
                "[RESPALDO] %s no atiende (%s): va a %s", role, e.cause, cfg.get("model")
            )
            self.respaldos.add(role)
            local = {k: cfg.get(k) for k in _DEL_RESPALDO if cfg.get(k) is not None}
            return await adapter.generate(prompt, role=role, **{**kwargs, **local})

    async def close(self) -> None:
        """Cierra cada adapter una sola vez (varios roles pueden compartir uno)."""
        seen: list[LLMProvider] = []
        respaldos = [adapter for adapter, _ in self._respaldo.values()]
        for adapter in [self._default, *self._by_role.values(), *respaldos]:
            if not any(adapter is s for s in seen):
                seen.append(adapter)
                await adapter.close()
