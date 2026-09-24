"""Doble de `anthropic.AsyncAnthropic` para tests (Spec-480): nunca llama a la API.

Registra los kwargs de cada `messages.create` y devuelve `anthropic.types.Message`
reales (mismos tipos que el SDK), así se prueba exactamente qué se envía y cómo se
lee la respuesta, sin gastar.
"""

from anthropic.types import (
    Message,
    RefusalStopDetails,
    TextBlock,
    ThinkingBlock,
    Usage,
)


def message(
    text: str = "Prosa del acto.",
    *,
    thinking: str | None = None,
    stop_reason: str = "end_turn",
    input_tokens: int = 1000,
    output_tokens: int = 800,
    refusal_category: str | None = None,
    model: str = "claude-sonnet-5",
) -> Message:
    """Respuesta armada a mano; con `thinking`, el primer bloque es de razonamiento."""
    content: list = []
    if thinking is not None:
        content.append(ThinkingBlock(type="thinking", thinking=thinking, signature="sig"))
    if text:
        content.append(TextBlock(type="text", text=text))
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model=model,
        content=content,
        stop_reason=stop_reason,
        stop_sequence=None,
        stop_details=(
            RefusalStopDetails(type="refusal", category=refusal_category, explanation="test")
            if stop_reason == "refusal"
            else None
        ),
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class FakeMessages:
    def __init__(self, responses: list[Message]):
        self.calls: list[dict] = []
        self._responses = list(responses)

    async def create(self, **kwargs) -> Message:
        self.calls.append(kwargs)
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]


class FakeAnthropic:
    """Reemplazo de `anthropic.AsyncAnthropic(api_key=...)`."""

    def __init__(self, responses: list[Message] | None = None):
        self.messages = FakeMessages(responses or [message()])
