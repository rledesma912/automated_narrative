"""Spec-720 S1: ¿Sonnet 5.5 arma y revisa los actos mejor que gemma?

Corre el Planificador y el Verificador reales (`OutlinePlanner`, `OutlineVerifier`,
prompts de `config/`) sobre historias de la copia de prod, con la config de los dos
roles cambiada en este script por variante:

- `gemma`: la de hoy en `hibrido-sonnet55` (gratis);
- `sonnet`: Sonnet 5.5 sin pensar;
- `sonnet_gastados`: igual, con la lista de recursos gastados en el Planificador (D9);
- `sonnet_piensa`: el Planificador pensando poco (D10).

Cuenta sin IA lo que ya se vio con gemma (recursos gastados, hechos de más, lugares
raros, personajes inventados, avisos de la IA, decisiones sin ubicar) y el costo real.
No guarda nada en la base. Sin `--yes` solo estima; `--tope` corta lo pago.

    uv run python scripts/research/720/medir_actos.py <salida.json> [--yes] [--tope 1.0]
        [--variantes sonnet,gemma] [--mock]

La salida va a data/dev/research_720/ (fuera de git: son historias reales).
"""

import argparse
import asyncio
import copy
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("LLM_PROFILE", "hibrido-sonnet55")

import src.config as config  # noqa: E402
from scripts.evaluate_voice import TokenMeter  # noqa: E402
from src.application.services import recursos_gastados  # noqa: E402
from src.application.services.authoring import elenco  # noqa: E402
from src.application.services.authoring.planner import OutlinePlanner  # noqa: E402
from src.application.services.authoring.verifier import OutlineVerifier  # noqa: E402
from src.infrastructure.database.repositories import SQLStoryRepository  # noqa: E402
from src.infrastructure.factories import LLMFactory  # noqa: E402

LARGAS = ["El trabajo de Yadira", "Los forasteros", "el engaño del diablo"]
CORTAS = ["El último cliente", "La criatura del río Paraná", "La conejita"]
HISTORIAS = LARGAS + CORTAS
LADO_A_LADO = ["El trabajo de Yadira", "La criatura del río Paraná"]

SONNET = {"provider": "anthropic", "model": "claude-sonnet-5-5", "thinking": "between_tools"}
VARIANTES = {
    # nombre: (historias, corridas, planificador, verificador, con la lista de gastados)
    "sonnet": (
        HISTORIAS,
        1,
        {**SONNET, "num_predict": 4000},
        {**SONNET, "num_predict": 2000},
        False,
    ),
    "sonnet_gastados": (
        ["El trabajo de Yadira", "Los forasteros", "La conejita"],
        1,
        {**SONNET, "num_predict": 4000},
        {**SONNET, "num_predict": 2000},
        True,
    ),
    "sonnet_piensa": (
        ["El trabajo de Yadira", "La criatura del río Paraná"],
        1,
        {**SONNET, "thinking": "adaptive", "effort": "low", "num_predict": 4000},
        {**SONNET, "num_predict": 2000},
        False,
    ),
    "gemma": (HISTORIAS, 2, None, None, False),  # None = la del perfil, tal cual
}
# Por escaleta (Planificador + Verificador), sin pensar / pensando (Spec-720 §1.3).
ESTIMADO = {"sonnet": 0.06, "sonnet_gastados": 0.06, "sonnet_piensa": 0.10, "gemma": 0.0}

# El bloque que sacó 9fab809 (Spec-680 D25), tal cual, para la variante D9.
GASTADOS = (
    "RECURSOS GASTADOS (ya se vieron en muchos cuentos: no los uses como hechos; si hace "
    "falta una señal, buscá una propia de este lugar y de estos personajes):\n{recursos}\n\n"
)
ANTES_DE = "ESCENARIOS YA DEFINIDOS:"
RARO = re.compile(r"_|,|/| - | y ", re.I)


def _worn(story):
    return recursos_gastados.sin_los_del_autor(
        recursos_gastados.hechos(), recursos_gastados.author_text(story)
    )


class PlannerConGastados(OutlinePlanner):
    def _prompt(self, story) -> str:
        prompt = super()._prompt(story)
        worn = _worn(story)
        if not worn or "RECURSOS GASTADOS" in prompt:  # desde S4 la trae el Planificador
            return prompt
        assert ANTES_DE in prompt, "el prompt del Planificador cambió"
        lines = "\n".join(f"- {r.nombre}" for r in worn)
        return prompt.replace(ANTES_DE, GASTADOS.format(recursos=lines) + ANTES_DE, 1)


def _con_roles(base: dict, planificador: dict | None, verificador: dict | None) -> None:
    """Cambia la config de los roles en el perfil activo (solo en este proceso)."""
    roles = config._profile["roles"]
    roles["planificador"] = copy.deepcopy(planificador or base["planificador"])
    roles["verificador"] = copy.deepcopy(verificador or base["verificador"])


def _metricas(story, acts, checked, planner) -> dict:
    estructura = planner.prompt_builder.estructura(story)
    worn = _worn(story)
    gastados = [
        {"acto": a.number, "recurso": r.id, "texto": hit}
        for a in acts
        for r in worn
        if (hit := r.en(" ".join(a.events)))
    ]
    sobre = [
        {"acto": a.number, "hechos": len(a.events), "max": estructura.acto(a.number)["hechos_max"]}
        for a in acts
        if estructura.acto(a.number).get("hechos_max")
        and len(a.events) > estructura.acto(a.number)["hechos_max"]
    ]
    avisos = [w for a in checked.outline for w in a.warnings]
    return {
        "gastados": gastados,
        "sobre_max": sobre,
        "lugares": [a.scenario for a in acts],
        "lugares_raros": [a.scenario for a in acts if RARO.search(a.scenario)],
        "elenco": [w.subject or w.key for w in avisos if w.key.startswith("elenco:")],
        "avisos_ia": [w.text for w in avisos if w.key.startswith("ia:")],
        "sin_ubicar": checked.missing_decisions,
        "actos": [
            {
                "numero": a.number,
                "objetivo": a.goal,
                "hechos": a.events,
                "escenario": a.scenario,
                "en_escena": a.on_stage,
            }
            for a in acts
        ],
    }


def _lado_a_lado(rows: list[dict]) -> str:
    out = ["# Spec-720: escaletas lado a lado (gemma | Sonnet)\n"]
    for title in LADO_A_LADO:
        pair = {
            v: next((r for r in rows if r["historia"] == title and r["variante"] == v), None)
            for v in ("gemma", "sonnet")
        }
        if not all(pair.values()):
            continue
        out.append(f"\n## {title}\n")
        for v, r in pair.items():
            out.append(f"\n### {v}\n")
            for a in r["actos"]:
                out.append(f"\n**Acto {a['numero']}** — {a['escenario']}  \n*{a['objetivo']}*\n")
                out.extend(f"- {h}" for h in a["hechos"])
                out.append(f"\nEn escena: {', '.join(a['en_escena'])}")
            if r["avisos_ia"]:
                out.append("\n**Avisos de la IA:**")
                out.extend(f"- {t}" for t in r["avisos_ia"])
    return "\n".join(out) + "\n"


async def main(args) -> None:
    out = Path(args.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    variantes = args.variantes.split(",") if args.variantes else list(VARIANTES)
    estimado = sum(
        ESTIMADO[v] * len(VARIANTES[v][0]) * VARIANTES[v][1] for v in variantes if not args.mock
    )
    print(f"Costo estimado: US$ {estimado:.2f} (tope US$ {args.tope:.2f})", flush=True)
    if estimado and not args.yes:
        print("Sin --yes no se corre nada pago.")
        return

    base = copy.deepcopy(config._profile["roles"])
    repo = SQLStoryRepository()
    by_title = {s.title: s for s in await repo.list_all()}
    rows, gastado = [], 0.0
    for variante in variantes:
        titles, runs, plan_cfg, verif_cfg, con_gastados = VARIANTES[variante]
        if args.historias:
            titles = [t for t in titles if t in args.historias.split(",")]
        _con_roles(base, plan_cfg, verif_cfg)
        for title in titles:
            for run in range(1, runs + 1):
                if gastado + ESTIMADO[variante] > args.tope and not args.mock:
                    print(f"Tope: US$ {gastado:.3f} gastados; corto antes de {variante}/{title}")
                    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
                    return
                llm = TokenMeter(LLMFactory.get_provider(use_mock=args.mock))
                story = await repo.get_by_id(by_title[title].id)
                planner = (PlannerConGastados if con_gastados else OutlinePlanner)(llm)
                start = time.monotonic()
                try:
                    acts, _ = await planner.plan(story)
                    plan_s = time.monotonic() - start
                    story = elenco.con_personajes(
                        story, elenco.personajes_de_la_autora(story, acts)
                    )  # como el job (Spec-700 D22)
                    checked = await OutlineVerifier(llm).verify(story, acts)
                    row = _metricas(story, acts, checked, planner)
                    error = ""
                except Exception as e:  # noqa: BLE001 — se mide, no se corrige
                    plan_s, row, error = time.monotonic() - start, {}, f"{type(e).__name__}: {e}"
                costo = llm.cost_usd() if variante != "gemma" else 0.0
                gastado += costo
                rows.append(
                    {
                        "historia": title,
                        "variante": variante,
                        "corrida": run,
                        "segundos_plan": round(plan_s, 1),
                        "segundos_total": round(time.monotonic() - start, 1),
                        "costo_usd": round(costo, 4),
                        "tokens": llm.usage,
                        "error": error[:300],
                        **row,
                    }
                )
                print(
                    f"{variante:15} {title[:26]:26} #{run} {rows[-1]['segundos_total']:6}s "
                    f"US$ {costo:.3f} gastados={len(row.get('gastados', []))} "
                    f"sobre={len(row.get('sobre_max', []))} raros={len(row.get('lugares_raros', []))} "
                    f"elenco={len(row.get('elenco', []))} ia={len(row.get('avisos_ia', []))} "
                    f"sin_ubicar={len(row.get('sin_ubicar', []))} {error[:80]}",
                    flush=True,
                )
                out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
                await llm.close()
    out.with_suffix(".md").write_text(_lado_a_lado(rows), "utf-8")
    print(f"Gastado: US$ {gastado:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("salida")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--tope", type=float, default=1.0)
    parser.add_argument("--variantes", default="")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--historias", default="", help="títulos separados por coma")
    asyncio.run(main(parser.parse_args()))
