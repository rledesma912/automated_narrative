"""Spec-480 T0.2: despacho por rol."""

from src.domain.interfaces import LLMResponse
from src.infrastructure.adapters import RoleRoutingAdapter


class FakeAdapter:
    def __init__(self, name: str):
        self.name = name
        self.calls: list[dict] = []
        self.closed = 0

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        self.calls.append({"prompt": prompt, **kwargs})
        return LLMResponse(text=f"{self.name}: {prompt}")

    async def close(self) -> None:
        self.closed += 1


async def test_despacha_por_rol_y_pasa_los_argumentos():
    local, claude = FakeAdapter("local"), FakeAdapter("claude")
    router = RoleRoutingAdapter({"voz": claude, "journal": local}, default=local)

    voz = await router.generate("acto", role="voz", system_prompt="S", model="claude-sonnet-5")
    journal = await router.generate("json", role="journal", model="gemma3:12b")

    assert (voz.text, journal.text) == ("claude: acto", "local: json")
    assert claude.calls == [
        {"prompt": "acto", "role": "voz", "system_prompt": "S", "model": "claude-sonnet-5"}
    ]


async def test_sin_rol_o_rol_desconocido_va_al_por_defecto():
    local, claude = FakeAdapter("local"), FakeAdapter("claude")
    router = RoleRoutingAdapter({"voz": claude}, default=local)

    assert (await router.generate("a")).text == "local: a"
    assert (await router.generate("b", role="otro")).text == "local: b"


async def test_close_una_vez_por_adapter():
    local, claude = FakeAdapter("local"), FakeAdapter("claude")
    router = RoleRoutingAdapter(
        {"story_analyst": local, "director": local, "voz": claude, "journal": local}, default=local
    )

    await router.close()

    assert (local.closed, claude.closed) == (1, 1)
