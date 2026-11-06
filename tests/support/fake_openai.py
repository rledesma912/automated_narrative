"""Doble de `openai.AsyncOpenAI` para tests (Spec-740 Parte F): nunca llama a la API.

Registra los kwargs de cada `chat.completions.create` y devuelve `ChatCompletion` reales
(mismos tipos que el SDK), así se prueba qué se envía y cómo se lee la respuesta.
"""

import httpx
import openai
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice


def completion(
    text: str | None = "Prosa del acto.",
    *,
    finish_reason: str = "stop",
    refusal: str | None = None,
    input_tokens: int = 1000,
    output_tokens: int = 800,
    model: str = "gpt-5-mini-2026-01-01",
    without_choices: bool = False,
) -> ChatCompletion:
    """Respuesta armada a mano."""
    choices = (
        []
        if without_choices
        else [
            Choice(
                index=0,
                finish_reason=finish_reason,
                message=ChatCompletionMessage(role="assistant", content=text, refusal=refusal),
            )
        ]
    )
    return ChatCompletion(
        id="chatcmpl-test",
        object="chat.completion",
        created=0,
        model=model,
        choices=choices,
        usage=CompletionUsage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
    )


def status_error(status: int, *, code: str | None = None, text: str = "x") -> openai.APIStatusError:
    """El error que arma el SDK para un HTTP `status` (con el `error.code` del cuerpo)."""
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status, request=request)
    classes = {
        400: openai.BadRequestError,
        401: openai.AuthenticationError,
        403: openai.PermissionDeniedError,
        429: openai.RateLimitError,
    }
    cls = classes.get(
        status, openai.InternalServerError if status >= 500 else openai.APIStatusError
    )
    return cls(text, response=response, body={"message": text, "code": code, "type": code})


def connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    )


class FakeCompletions:
    def __init__(self, responses: list):
        self.calls: list[dict] = []
        self._responses = list(responses)

    async def create(self, **kwargs) -> ChatCompletion:
        self.calls.append(kwargs)
        item = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        if isinstance(item, Exception):
            raise item
        return item


class FakeChat:
    def __init__(self, responses: list):
        self.completions = FakeCompletions(responses)


class FakeOpenAI:
    """Reemplazo de `openai.AsyncOpenAI(api_key=..., max_retries=0)`."""

    def __init__(self, responses: list | None = None):
        self.chat = FakeChat(responses or [completion()])
