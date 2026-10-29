"""Spec-700 T4.1: ¿gemma marca las respuestas que la idea nueva contradice, y solo esas?

Para cada caso, toma la historia de la copia local de prod, le cambia la idea a mano de
dos maneras y corre el servicio real (`RevisorDeRespuestas`, prompts de `config/`) con
el rol `consultor` del perfil híbrido (gemma3:12b, gratis):

- «contradice»: un cambio que choca con una respuesta conocida (`espera`);
- «reescrita»: un cambio que no contradice nada (no debería marcar ninguna).

No toca la base.

    uv run python scripts/research/700/medir_revisor.py <salida.json> [corridas]

La salida va a data/dev/research_700/ (fuera de git: son historias reales).
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("LLM_PROFILE", "hibrido-sonnet55")

from src.application.services.authoring import context, workshop_rules  # noqa: E402
from src.application.services.authoring.revisor import RevisorDeRespuestas  # noqa: E402
from src.infrastructure.database.repositories import SQLStoryRepository  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

# (historia, criterio que tiene que marcar, (viejo, nuevo) para contradecir, agregado neutro)
CASOS = [
    (
        "El trabajo de Yadira",
        "final",
        (
            "El problema es que Ximena no sabe si realmente está siendo víctima de una "
            "maldición, ni qué puede hacer para detenerla.",
            "Ximena decide no irse: se queda en el pueblo, enfrenta a Yadira y a Doña Aurelia, "
            "y el trabajo se rompe. Al final sigue viviendo ahí con Gael, tranquila.",
        ),
        " Ximena atiende la tienda de abarrotes de su mamá.",
    ),
    (
        "La criatura del río Paraná",
        "vulnerabilidad",
        (
            "Cerca de las tres de la mañana, agotado después de haber trabajado durante el "
            "día, Marcelo se queda dormido en la garita. Al despertar, descubre",
            "Marcelo está bien despierto: tomó mucho café y no se duerme ni un minuto en toda "
            "la noche. Cerca de las tres de la mañana descubre",
        ),
        " Marcelo tiene dos hijos y vive a unas cuadras de la terminal.",
    ),
    (
        "El empleado del maletín",
        "casa_detalle",
        (
            "Estaba empapado, llevaba un maletín de cuero y parecía genuinamente desesperado.",
            "Estaba empapado, llevaba un maletín de cuero y parecía genuinamente desesperado. "
            "Tenía las dos manos al descubierto, sin ninguna venda ni marca, y nunca se las tocaba.",
        ),
        " Esa noche Iván había llevado un termo de café para no dormirse.",
    ),
    (
        "Los forasteros",
        "descubrimiento",
        (
            "tenia cara deforme y sus patas eran de cabra y caminaba por las paredes.",
            "tenia cara de viejo y manos larguisimas con garras, pero las piernas eran de "
            "bebe, normales, y caminaba por las paredes agarrandose con las manos.",
        ),
        " la chacra quedaba cerca de un arroyo.",
    ),
    (
        "NO TE DETENGAS EN EL BOSQUE",
        "meta",
        (
            "Un camionero que viaja de madrugada por una ruta rodeada de bosque",
            "Un camionero que ya entregó toda la carga y vuelve con el camión vacío, sin "
            "ningún apuro, viaja de madrugada por una ruta rodeada de bosque",
        ),
        " Es invierno y hace mucho frío.",
    ),
    (
        "El último cliente",
        "final",
        (
            "Lautaro cuenta que al final corrió hasta la casa, despertó a su padre y ambos "
            "salieron con una linterna para revisar. Pero el negocio vacío.",
            "Lautaro no logra salir: se queda encerrado en el depósito hasta que amanece, solo, "
            "sin animarse a pedir ayuda, y nunca le cuenta a nadie lo que pasó.",
        ),
        " El almacén tiene un gato que duerme arriba de la heladera.",
    ),
]


def _con_idea(story, idea: str):
    """La historia con la idea cambiada y la de antes como la última que leyó «Preguntas»."""
    story = context.con_idea_leida(story, "preguntas")
    if story.direction.premise:
        return story.model_copy(
            update={"direction": story.direction.model_copy(update={"premise": idea})}
        )
    return story.model_copy(update={"sinopsis": idea})


async def main(out: Path, runs: int) -> None:
    repo = SQLStoryRepository()
    by_title = {s.title: s for s in await repo.list_all()}
    llm = LLMFactory.get_provider()
    rows = []
    for title, espera, (viejo, nuevo), agregado in CASOS:
        story = await repo.get_by_id(by_title[title].id)
        idea = story.direction.premise if story.direction and story.direction.premise else ""
        idea = idea or story.sinopsis
        assert viejo in idea, f"{title}: no encuentro el texto a cambiar"
        variantes = {
            "contradice": idea.replace(viejo, nuevo),
            "reescrita": idea.rstrip() + agregado,
        }
        for variante, texto in variantes.items():
            for run in range(1, runs + 1):
                start = time.monotonic()
                changed = await RevisorDeRespuestas(llm).revisar(_con_idea(story, texto))
                marcas = {
                    w.criterion: workshop_rules.no_coincide(w)
                    for w in changed
                    if workshop_rules.no_coincide(w)
                }
                rows.append(
                    {
                        "historia": title,
                        "variante": variante,
                        "corrida": run,
                        "espera": espera if variante == "contradice" else "",
                        "marcas": marcas,
                        "segundos": round(time.monotonic() - start, 1),
                    }
                )
                print(f"{title[:26]:26} {variante:10} #{run} {marcas}", flush=True)
                out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    close = getattr(llm, "close", None)
    if close:
        await close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 2))
