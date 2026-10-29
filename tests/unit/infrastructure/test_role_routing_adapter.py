"""Spec-480 T0.2: despacho por rol."""

import pytest

from src.domain.exceptions import LLMResponseError, LLMUnavailableError
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
    router = RoleRoutingAdapter({"director": local, "voz": claude, "journal": local}, default=local)

    await router.close()

    assert (local.closed, claude.closed) == (1, 1)


# ── Spec-720 D6: el respaldo ────────────────────────────────────────────────


class Caido(FakeAdapter):
    def __init__(self, error: Exception):
        super().__init__("caído")
        self.error = error

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        self.calls.append({"prompt": prompt, **kwargs})
        raise self.error


GEMMA = {"provider": "ollama", "model": "gemma3:12b", "temperature": 0.4, "num_ctx": 8192}


async def test_si_la_nube_no_atiende_responde_el_respaldo_con_su_config():
    local = FakeAdapter("local")
    nube = Caido(LLMUnavailableError("credito", "Sin crédito."))
    router = RoleRoutingAdapter(
        {"planificador": nube}, default=local, respaldo={"planificador": (local, GEMMA)}
    )

    r = await router.generate(
        "actos",
        role="planificador",
        model="claude-sonnet-5-5",
        num_predict=4000,
        response_schema={"type": "object"},
    )

    assert r.text == "local: actos"
    assert local.calls == [
        {
            "prompt": "actos",
            "role": "planificador",
            "model": "gemma3:12b",
            "temperature": 0.4,
            "num_ctx": 8192,
            "num_predict": 4000,  # el respaldo no lo declara: sigue el de la llamada
            "response_schema": {"type": "object"},
        }
    ]
    assert router.respaldos == {"planificador"}


async def test_sin_respaldo_o_con_otro_error_falla_como_siempre():
    local = FakeAdapter("local")
    caida = Caido(LLMUnavailableError("credito", "Sin crédito."))
    router = RoleRoutingAdapter({"voz": caida}, default=local)
    with pytest.raises(LLMUnavailableError):
        await router.generate("acto", role="voz")

    rara = Caido(LLMResponseError("respuesta rara"))
    router = RoleRoutingAdapter(
        {"planificador": rara}, default=local, respaldo={"planificador": (local, GEMMA)}
    )
    with pytest.raises(LLMResponseError):
        await router.generate("actos", role="planificador")
    assert router.respaldos == set() and local.calls == []


async def test_close_cierra_tambien_el_respaldo():
    nube, local = FakeAdapter("nube"), FakeAdapter("local")
    router = RoleRoutingAdapter(
        {"planificador": nube}, default=nube, respaldo={"planificador": (local, GEMMA)}
    )
    await router.close()
    assert (nube.closed, local.closed) == (1, 1)
