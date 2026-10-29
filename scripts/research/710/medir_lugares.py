"""Spec-710 D6: ¿gemma da un lugar por hecho, sin lugares compuestos?

Corre el Planificador real (`OutlinePlanner`, prompts de `config/`) con el rol
`planificador` del perfil híbrido (gemma3:12b, gratis) sobre las historias de la copia
local de prod, con una variante: cada hecho trae su lugar (`{texto, lugar}`) y el acto ya
no trae «escenario». No toca la base ni `config/`: la variante vive en este script.

    uv run python scripts/research/710/medir_lugares.py <salida.json> [corridas] [titulo...]

La salida va a data/dev/research_710/ (fuera de git: son historias reales).
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from pydantic import BaseModel, model_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("LLM_PROFILE", "hibrido-sonnet55")

from src.application.services.authoring.planner import ROLE, ActoPlan, OutlinePlanner  # noqa: E402
from src.application.services.authoring.structured_llm import generate_structured  # noqa: E402
from src.infrastructure.database.repositories import SQLStoryRepository  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

HECHOS_VIEJO = '- "hechos": {n} concretos y en orden, con acciones del protagonista.'
HECHOS_NUEVO = (
    '- "hechos": {n} concretos y en orden, con acciones del protagonista. Cada hecho es '
    '{{"texto": …, "lugar": …}}: "lugar" es DÓNDE pasa ese hecho, UN solo lugar, corto '
    "(sin comas, barras ni «y»). Si el hecho pasa donde el anterior, repetí el mismo nombre."
)
ESCENARIO = '- "escenario": dónde ocurre.\n'
COMPUESTO = re.compile(r",|/| - | y |\be\b", re.I)


class Hecho(BaseModel):
    texto: str
    lugar: str


class ActoLugares(ActoPlan):
    hechos: list[Hecho]  # type: ignore[assignment]
    escenario: str = ""


def escaleta_lugares(num_actos: int) -> type[BaseModel]:
    class Escaleta(BaseModel):
        actos: list[ActoLugares]

        @model_validator(mode="after")
        def _completa(self):
            if sorted(a.numero for a in self.actos) != list(range(1, num_actos + 1)):
                raise ValueError(f"faltan actos: {[a.numero for a in self.actos]}")
            if any(not a.hechos for a in self.actos):
                raise ValueError("acto sin hechos")
            return self

    return Escaleta


class PlannerLugares(OutlinePlanner):
    def _prompt(self, story) -> str:
        n = self.prompt_builder.estructura(story).hechos_por_acto
        prompt = super()._prompt(story)
        viejo = HECHOS_VIEJO.format(n=n)
        assert viejo in prompt and ESCENARIO in prompt, "el prompt del Planificador cambió"
        return prompt.replace(viejo, HECHOS_NUEVO.format(n=n)).replace(ESCENARIO, "")

    async def plan_lugares(self, story):
        estructura = self.prompt_builder.estructura(story)
        return await generate_structured(
            self.llm,
            role=ROLE,
            prompt=self._prompt(story),
            system_prompt=self.system_prompt(story),
            output=escaleta_lugares(estructura.num_actos),
        )


async def main(out: Path, runs: int, titles: list[str]) -> None:
    repo = SQLStoryRepository()
    llm = LLMFactory.get_provider()
    planner = PlannerLugares(llm)
    rows = []
    for summary in await repo.list_all():
        story = await repo.get_by_id(summary.id)
        if titles and story.title not in titles:
            continue
        for run in range(1, runs + 1):
            start = time.monotonic()
            try:
                result, _ = await planner.plan_lugares(story)
                actos = [
                    {
                        "numero": a.numero,
                        "hechos": [{"texto": h.texto, "lugar": h.lugar} for h in a.hechos],
                    }
                    for a in sorted(result.actos, key=lambda a: a.numero)
                ]
                error = ""
            except Exception as e:  # noqa: BLE001 — se mide, no se corrige
                actos, error = [], f"{type(e).__name__}: {e}"[:300]
            hechos = [h for a in actos for h in a["hechos"]]
            vacios = sum(1 for h in hechos if not h["lugar"].strip())
            compuestos = [h["lugar"] for h in hechos if COMPUESTO.search(h["lugar"])]
            rows.append(
                {
                    "historia": story.title,
                    "corrida": run,
                    "segundos": round(time.monotonic() - start, 1),
                    "error": error,
                    "hechos": len(hechos),
                    "sin_lugar": vacios,
                    "compuestos": compuestos,
                    "lugares": list(dict.fromkeys(h["lugar"] for h in hechos)),
                    "actos": actos,
                }
            )
            print(
                f"{story.title[:28]:28} #{run} hechos={len(hechos)} sin_lugar={vacios} "
                f"compuestos={len(compuestos)} lugares={len(rows[-1]['lugares'])} {error}",
                flush=True,
            )
            out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    close = getattr(llm, "close", None)
    if close:
        await close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 2, sys.argv[3:]))
