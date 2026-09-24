"""Adapter que despacha cada llamada al proveedor de su rol (Spec-480).

Permite perfiles mixtos: por ejemplo, la Voz en Anthropic y el resto en Ollama.
Todas las llamadas del pipeline pasan `role`, así que el ruteo es por rol.
"""

from src.domain.interfaces import LLMProvider, LLMResponse


class RoleRoutingAdapter:
    """`LLMProvider` compuesto: un adapter por rol y uno por defecto."""

    def __init__(self, by_role: dict[str, LLMProvider], default: LLMProvider) -> None:
        self._by_role = dict(by_role)
        self._default = default

    def adapter_for(self, role: str | None) -> LLMProvider:
        """Adapter del rol; sin rol o con un rol desconocido, el por defecto."""
        return self._by_role.get(role or "", self._default)

    async def generate(self, prompt: str, *, role: str | None = None, **kwargs) -> LLMResponse:
        return await self.adapter_for(role).generate(prompt, role=role, **kwargs)

    async def close(self) -> None:
        """Cierra cada adapter una sola vez (varios roles pueden compartir uno)."""
        seen: list[LLMProvider] = []
        for adapter in [self._default, *self._by_role.values()]:
            if not any(adapter is s for s in seen):
                seen.append(adapter)
                await adapter.close()
