"""Spec-690: ¿gemma encuentra el final dentro de «¿De qué trata?»?

Lee las historias de la copia local de prod y, para cada idea, corre el servicio real
(`FinalDeLaIdea`, prompts de `config/`) con el rol `consultor` del perfil híbrido
(gemma3:12b, gratis). Guarda el final que sacó junto al «¿Cómo termina?» que escribió
la autora. No toca la base: arma cada historia sin el final viejo ni el taller.

    uv run python scripts/research/690/medir_final.py <salida.json> [corridas]

La salida va a data/dev/research_final/ (fuera de git: son historias reales).
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("LLM_PROFILE", "hibrido-sonnet55")

from src.application.services.authoring.final_de_la_idea import FinalDeLaIdea  # noqa: E402
from src.infrastructure.database.repositories import SQLStoryRepository  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402


async def main(out: Path, runs: int) -> None:
    repo = SQLStoryRepository()
    llm = LLMFactory.get_provider()
    rows = []
    for summary in await repo.list_all():
        story = await repo.get_by_id(summary.id)
        if not story.direction or not story.direction.premise.strip():
            continue
        ending = story.direction.ending
        bare = story.model_copy(
            update={"direction": story.direction.model_copy(update={"ending": ""}), "workshop": []}
        )
        for run in range(1, runs + 1):
            start = time.monotonic()
            item = await FinalDeLaIdea(llm).ensure(bare)
            final = item.answer if item else ""
            rows.append(
                {
                    "historia": story.title,
                    "corrida": run,
                    "final_ia": final,
                    "final_autora": ending,
                    "segundos": round(time.monotonic() - start, 1),
                }
            )
            print(f"{story.title[:28]:28} #{run} {final[:100]!r}", flush=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    close = getattr(llm, "close", None)
    if close:
        await close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 2))
