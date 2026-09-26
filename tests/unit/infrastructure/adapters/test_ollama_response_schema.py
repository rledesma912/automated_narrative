"""Spec-530: el esquema de salida viaja como `format` a Ollama."""

import httpx

from src.infrastructure.adapters.ollama_adapter import OllamaAdapter


class _Resp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"response": "{}"}


def _capture(monkeypatch) -> list[dict]:
    payloads: list[dict] = []

    async def post(_self, _url, json):
        payloads.append(json)
        return _Resp()

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return payloads


async def test_response_schema_se_manda_como_format(monkeypatch):
    payloads = _capture(monkeypatch)
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    await OllamaAdapter(host="http://x").generate("p", model="m", response_schema=schema)
    assert payloads[0]["format"] == schema


async def test_sin_response_schema_no_hay_format(monkeypatch):
    payloads = _capture(monkeypatch)
    await OllamaAdapter(host="http://x").generate("p", model="m")
    assert "format" not in payloads[0]
