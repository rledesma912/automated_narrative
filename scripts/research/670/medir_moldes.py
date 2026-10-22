"""Spec-670 D7: la misma idea con varios moldes → ¿salen actos distintos y menos de manual?

uv run python scripts/research/670/medir_moldes.py <historia.yaml> <carpeta> forma[+giro] ...

Cada molde: una base temporal, la historia sin preguntas ni actos, y el Planificador +
el Verificador del perfil activo (`LLM_PROFILE`), como el job `plan_outline`. Guarda los
actos de cada uno y un resumen con las imágenes «de manual» que aparecen.
"""

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Imágenes de manual del género que ya se vieron en los relatos (§1.2, S1). Se siguen
# contando así para comparar con la medición de la 670; la Spec-680 suma `gastados`,
# con la lista de config/recursos_gastados.yaml (un hecho por recurso).
DE_MANUAL = [
    "huella",
    "ojos",
    "brillo",
    "sombra",
    "silueta",
    "figura",
    "golpe",
    "ladr",
    "chapoteo",
    "alarido",
    "grito",
    "rasguñ",
    "rasca",
]


async def main(src: Path, out: Path, moldes: list[str]) -> None:
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(tempfile.mkdtemp()) / 'm.db'}"
    from src.application.services import recursos_gastados
    from src.application.services.authoring import molde as molde_mod
    from src.application.services.authoring.planner import OutlinePlanner
    from src.application.services.authoring.verifier import OutlineVerifier
    from src.application.use_cases.create_story import CreateStoryUseCase
    from src.config import settings
    from src.infrastructure.database.connection import init_db
    from src.infrastructure.database.repositories import SQLGenreRepository, SQLStoryRepository
    from src.infrastructure.factories import LLMFactory
    from src.infrastructure.loaders import YamlStoryLoader

    settings.database_url = os.environ["DATABASE_URL"]
    await init_db()
    repo, genres = SQLStoryRepository(), SQLGenreRepository()
    llm = LLMFactory.get_provider()
    out.mkdir(parents=True, exist_ok=True)
    base = yaml.safe_load(src.read_text("utf-8"))
    for key in ("workshop", "taller", "escaleta", "outline"):
        base.pop(key, None)
    resumen = []
    for spec in moldes:
        forma, _, giro = spec.partition("+")
        data = json.loads(json.dumps(base))
        data["direction"].update({"form": forma if forma != "regla" else "", "ingredient": giro})
        story = await CreateStoryUseCase(repo, genres).execute(
            YamlStoryLoader().load_from_dict(data)
        )
        story = await repo.get_by_id(story.id)
        m = molde_mod.for_story(story)
        acts, t_plan = await OutlinePlanner(llm).plan(story)
        checked = await OutlineVerifier(llm).verify(story, acts)
        hechos = [h for a in checked.outline for h in a.events]
        texto = " ".join(hechos).lower()
        manual = {w: len(re.findall(w, texto)) for w in DE_MANUAL if w in texto}
        gastados = {
            r.id: n for r in recursos_gastados.hechos() if (n := sum(1 for h in hechos if r.en(h)))
        }
        actos = [
            {
                "numero": a.number,
                "hechos": a.events,
                "avisos": [w.text for w in a.warnings if not w.dismissed],
            }
            for a in checked.outline
        ]
        nombre = spec.replace("+", "_")
        (out / f"{nombre}.json").write_text(
            json.dumps(
                {
                    "molde": spec,
                    "forma": m.forma.nombre,
                    "giro": m.giro.nombre if m.giro else "",
                    "actos": actos,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "utf-8",
        )
        resumen.append(
            {
                "molde": spec,
                "hechos": len(hechos),
                "de_manual": manual,
                "total_de_manual": sum(manual.values()),
                "gastados": gastados,  # Spec-680
                "total_gastados": sum(gastados.values()),
            }
        )
        print(
            f"{spec}: {len(hechos)} hechos, de manual {sum(manual.values())} {manual}, "
            f"gastados {sum(gastados.values())} {gastados}"
        )
    (out / "resumen.json").write_text(
        json.dumps(
            {"perfil": settings.active_profile_name, "historia": src.name, "moldes": resumen},
            ensure_ascii=False,
            indent=2,
        ),
        "utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]))
