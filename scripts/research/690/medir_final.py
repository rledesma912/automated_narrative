"""Medición (próxima spec): ¿gemma encuentra el final dentro de «¿De qué trata?»?

Lee las 9 historias de la copia local de prod, le pide al rol `consultor` del perfil
híbrido (gemma3:12b) que diga si la idea cuenta cómo termina y que copie ese final, y
guarda lo que devuelve junto al «¿Cómo termina?» que escribió la autora.

    uv run python scripts/research/690/medir_final.py <salida.json> [corridas]

Variante 2 de la medición (la IA marca dónde empieza el final; el código toma desde ahí
hasta el final de la idea). La salida queda en data/dev/research_final/ (fuera de git:
son historias reales).
"""

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
os.environ["LLM_PROFILE"] = "hibrido-sonnet55"

from pydantic import BaseModel  # noqa: E402

from src.application.services.authoring.structured_llm import generate_structured  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

SYSTEM = """Sos un editor de cuentos de terror. Leés la idea de una historia, escrita por alguien que no sabe de escritura, y te fijás si ya cuenta cómo termina.

Reglas:
- "cuenta_final" es true solo si la idea dice qué pasa al final de la historia (cómo queda el protagonista, qué descubre, qué le queda después). Un hecho del medio no es el final.
- El final es lo que pasa DESPUÉS del momento más fuerte (el susto mayor, el enfrentamiento): cómo se salva o no, qué descubre después, cómo le quedó la vida. El momento más fuerte no es parte del final.
- Si es true, en "final" copiá TEXTUALMENTE solo la PRIMERA oración del final (la primera que viene después del momento más fuerte), sin cambiar ninguna palabra. Si es false, "final" va vacío.
- No inventes nada que no esté en la idea."""

PROMPT = """LA IDEA:
{idea}

Devolvé:
- "cuenta_final": true o false.
- "final": la primera oración del final, copiada tal cual ("" si no lo cuenta)."""


class Final(BaseModel):
    cuenta_final: bool
    final: str


async def main(out: Path, runs: int) -> None:
    db = sqlite3.connect("file:data/dev/stories.db?mode=ro", uri=True)
    stories = [
        (t, json.loads(d or "{}"))
        for t, d in db.execute("select title, direction from story order by created_at")
    ]
    llm = LLMFactory.get_provider()
    rows = []
    for title, d in stories:
        idea = d.get("premise", "")
        for run in range(1, runs + 1):
            result, secs = await generate_structured(
                llm,
                role="consultor",
                prompt=PROMPT.format(idea=idea),
                system_prompt=SYSTEM,
                output=Final,
            )
            flat, first = " ".join(idea.split()), " ".join(result.final.split()).strip('"«»')
            pos = flat.find(first[:60]) if first else -1
            copied = pos >= 0
            result.final = flat[pos:] if copied else result.final  # desde ahí hasta el final
            rows.append(
                {
                    "historia": title,
                    "corrida": run,
                    "cuenta_final": result.cuenta_final,
                    "final_ia": result.final,
                    "textual": copied,
                    "final_autora": d.get("ending", ""),
                    "segundos": round(secs, 1),
                }
            )
            print(
                f"{title[:28]:28} #{run} {result.cuenta_final!s:5} textual={copied!s:5} {secs:5.1f}s  {result.final[:90]!r}",
                flush=True,
            )
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    close = getattr(llm, "close", None)
    if close:
        await close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 2))
