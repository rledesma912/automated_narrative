# ruff: noqa — script de investigación de la Spec-530, se conserva tal como se corrió.
import json
import sqlite3
import time

import httpx

c = sqlite3.connect("/mnt/LLM/apps/automated_narrative/data/prod/stories.db")
syn = c.execute(
    "select sinopsis from story where id='4a4d8cab-178f-460c-ae46-9e6e067638fb'"
).fetchone()[0]
checks = {
    "meta": "¿El protagonista quiere algo concreto esa noche (una meta que la amenaza pueda frustrar)?",
    "agencia": "¿El protagonista HACE algo frente a la amenaza (actúa, investiga, huye, enfrenta) o solo la presencia/observa?",
    "escalada": "¿Cada encuentro con la amenaza es de un tipo distinto y más grave que el anterior, o se repite el mismo tipo de encuentro?",
    "en_juego": "¿Está claro qué pierde el protagonista si la amenaza sigue (trabajo, vida, cordura, alguien querido)?",
    "historia_secreta": "¿Hay una historia oculta que explique por qué le pasa a ÉL (un vínculo entre el protagonista y la amenaza)?",
    "siembra_cosecha": "¿Algo presentado al inicio se retoma y resignifica al final?",
    "cierre": "¿El final deja una marca o giro inquietante, o se resuelve de forma plana?",
}
schema = {
    "type": "object",
    "properties": {
        "evaluaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterio": {"type": "string", "enum": list(checks)},
                    "cumple": {"type": "string", "enum": ["si", "parcial", "no"]},
                    "evidencia": {"type": "string"},
                    "pregunta": {"type": "string"},
                    "opciones": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["criterio", "cumple", "evidencia", "pregunta", "opciones"],
            },
        }
    },
    "required": ["evaluaciones"],
}
prompt = (
    """Sos un editor de cuentos de terror. Evaluá la SINOPSIS contra cada CRITERIO.
Para cada criterio: "cumple" (si/parcial/no), "evidencia" (cita breve de la sinopsis o "no aparece"),
y si no cumple del todo, UNA pregunta concreta al autor sobre ESTA historia (no genérica) y 3 opciones
cortas y distintas entre sí que el autor pueda elegir. Si cumple, pregunta y opciones vacías.
No reescribas la historia. Español rioplatense.

CRITERIOS:
"""
    + "\n".join(f"- {k}: {v}" for k, v in checks.items())
    + f"\n\nSINOPSIS:\n{syn}"
)
for run in range(2):
    t = time.time()
    r = httpx.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "gemma3:12b",
            "stream": False,
            "format": schema,
            "options": {"temperature": 0.3, "num_ctx": 8192},
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=600,
    )
    out = json.loads(r.json()["message"]["content"])
    print(f"=== corrida {run + 1}: {time.time() - t:.0f}s")
    for e in out["evaluaciones"]:
        print(f"[{e['criterio']}] {e['cumple']} — {e['evidencia'][:110]}")
        if e["pregunta"]:
            print("   ?", e["pregunta"])
            [print("     ·", o) for o in e["opciones"]]
