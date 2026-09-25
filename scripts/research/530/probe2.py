# ruff: noqa — script de investigación de la Spec-530, se conserva tal como se corrió.
import json
import time

import httpx

src = open("probe.py").read()
exec(src.split("for run in range")[0])  # reuse checks, schema, prompt, syn
objetivo = """CONTEXTO: Estamos ayudando a un autor amateur a preparar un cuento de terror que después se genera
automáticamente en 5 actos (unas 2.500 palabras) y se escucha como audio. El autor eligió como dirección:
un fantasma de ruta, efecto buscado = pavor creciente con un final melancólico e inquietante.
Tus preguntas tienen que servir para que la historia tenga más material dramático, sin cambiar lo que el autor quiere contar.
"""
teoria = """MARCO TEÓRICO: La generación usa la pirámide de Freytag (exposición, acción ascendente, clímax,
acción descendente, desenlace) y los pilares aristotélicos: hamartia (falla trágica del protagonista),
hybris, anagnórisis (reconocimiento), peripecia (giro de fortuna) y un residuo final.
"""
for label, ctx in [("objetivo", objetivo), ("objetivo+teoria", objetivo + teoria)]:
    p = ctx + "\n" + prompt
    t = time.time()
    r = httpx.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "gemma3:12b",
            "stream": False,
            "format": schema,
            "options": {"temperature": 0.3, "num_ctx": 8192},
            "messages": [{"role": "user", "content": p}],
        },
        timeout=600,
    )
    out = json.loads(r.json()["message"]["content"])
    print(f"\n######## {label}: {time.time() - t:.0f}s")
    for e in out["evaluaciones"]:
        print(f"[{e['criterio']}] {e['cumple']}")
        if e["pregunta"]:
            print("   ?", e["pregunta"])
            [print("     ·", o) for o in e["opciones"]]
