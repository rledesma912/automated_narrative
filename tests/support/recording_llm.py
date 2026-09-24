"""LLM de prueba que graba cada llamada y responde en el formato de cada rol.

Responde lo que parsea cada rol (secciones del Analyst, ESCENARIO/EVENTOS del
Mapper, JSON del Journal, prosa de la Voz) para que el pipeline recorra sus
caminos normales y no los de fallback. Determinístico: misma historia, mismos
prompts.
"""

import json
import re
from dataclasses import dataclass, field

from src.domain.interfaces import LLMResponse

_PILLARS = (
    "resonance_hamartia",
    "resonance_hybris",
    "resonance_anagnorisis",
    "resonance_peripeteia",
    "resonance_residual",
)


@dataclass
class RecordingLLM:
    calls: list[dict] = field(default_factory=list)
    journal_extra: dict = field(default_factory=dict)

    async def generate(self, prompt: str, *, system_prompt: str | None = None, role=None, **_kw):
        self.calls.append({"role": role, "system": system_prompt or "", "prompt": prompt})
        return LLMResponse(text=self._answer(role, prompt), context=None)

    def _answer(self, role: str | None, prompt: str) -> str:
        n = len([c for c in self.calls if c["role"] == role])
        if role == "story_analyst":
            return "\n\n".join(
                f"## {p}\nPilar {i} de la historia." for i, p in enumerate(_PILLARS, 1)
            )
        if role == "director":
            return f"ESCENARIO: El galpón\nEVENTOS:\n- Rosa hace algo en el acto {n}."
        if role == "journal":
            beat = re.search(r"Beat #(\d+)", prompt)
            data = {
                "last_events": f"Pasó lo del acto {beat.group(1) if beat else n}.",
                "unresolved_mysteries": "¿Quién silbaba?",
                "physical_emotional_state": "Rosa, cansada.",
                **self.journal_extra,
            }
            return json.dumps(data, ensure_ascii=False)
        return f"Prosa del acto {n}. Rosa camina por el galpón y escucha algo."

    async def close(self) -> None:
        pass
