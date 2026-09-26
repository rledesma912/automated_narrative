"""LLM de prueba que graba cada llamada y responde en el formato de cada rol.

Las llamadas con esquema (Planificador, Verificador, memoria, Consultor) reciben el
JSON del mock del asistente; la Voz, prosa. Determinístico: misma historia, mismos
prompts.
"""

import json
from dataclasses import dataclass, field

from src.domain.interfaces import LLMResponse
from src.infrastructure.adapters.mock_structured import mock_structured


@dataclass
class RecordingLLM:
    calls: list[dict] = field(default_factory=list)

    async def generate(
        self, prompt: str, *, system_prompt: str | None = None, role=None, **kw
    ) -> LLMResponse:
        self.calls.append({"role": role, "system": system_prompt or "", "prompt": prompt})
        schema = kw.get("response_schema")
        if schema:
            text = json.dumps(mock_structured(role, schema), ensure_ascii=False)
        else:
            n = len([c for c in self.calls if c["role"] == role])
            text = f"Prosa del acto {n}. Rosa camina por el galpón y escucha algo."
        return LLMResponse(text=text, context=None)

    async def close(self) -> None:
        pass
