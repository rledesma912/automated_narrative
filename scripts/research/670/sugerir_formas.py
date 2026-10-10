"""Spec-670 T4.2: qué forma sugiere la IA para cada historia (criterio 6 de la spec).

uv run python scripts/research/670/sugerir_formas.py <salida.json> <historia.yaml>...

Importa los YAML en una base temporal (no toca dev ni prod) y llama al FormSuggester con
el perfil activo (`LLM_PROFILE`). Cada historia es una llamada paga si el perfil usa Claude.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


async def main(out: Path, files: list[Path]) -> None:
    tmp = Path(tempfile.mkdtemp()) / "sugerir.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp}"
    from src.application.services.authoring.form_suggester import FormSuggester
    from src.application.use_cases.create_story import CreateStoryUseCase
    from src.config import settings
    from src.infrastructure.database.connection import init_db
    from src.infrastructure.database.repositories import SQLGenreRepository, SQLStoryRepository
    from src.infrastructure.factories import LLMFactory
    from src.infrastructure.loaders import YamlStoryLoader

    settings.database_url = os.environ["DATABASE_URL"]
    await init_db()
    repo, genres = SQLStoryRepository(), SQLGenreRepository()
    suggester = FormSuggester(LLMFactory.get_provider())
    results = []
    for f in files:
        story = await CreateStoryUseCase(repo, genres).execute(
            YamlStoryLoader().load(f.read_text("utf-8"))
        )
        story = await repo.get_by_id(story.id)
        s, elapsed = await suggester.suggest(story)
        results.append(
            {
                "historia": story.title,
                "forma": s.form,
                "motivo": s.reason,
                "arco": s.arc,
                "segundos": round(elapsed, 1),
            }
        )
        print(f"{story.title}: {s.form} — {s.reason}" + (f" [{s.arc}]" if s.arc else ""))
    out.write_text(
        json.dumps(
            {"perfil": settings.active_profile_name, "resultados": results},
            ensure_ascii=False,
            indent=2,
        ),
        "utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]))
