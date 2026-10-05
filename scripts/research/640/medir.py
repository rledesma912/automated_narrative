"""Spec-640: mide las versiones de «el engaño del diablo» de dev (sin IA).

uv run python scripts/research/640/medir.py <carpeta> <narrative_id>...
Guarda el texto de cada versión y un resumen.json con las métricas de voice_metrics.
"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.voice_metrics import evaluate  # noqa: E402

API = "http://localhost:8040/api/v1"
FRASES = ["pasó lo peor", "lo peor fue", "era lo peor", "se esfuma", "se lo tragó"]

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
resumen = {}
for nid in sys.argv[2:]:
    with urllib.request.urlopen(f"{API}/generated-narratives/{nid}") as r:
        text = json.load(r)["content"]
    (out / f"{nid}.md").write_text(text, encoding="utf-8")
    m = evaluate(text, "Susana", [])
    m["frases_640"] = {f: text.lower().count(f) for f in FRASES if f in text.lower()}
    resumen[nid] = m
(out / "resumen.json").write_text(
    json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
)
for nid, m in resumen.items():
    print(
        nid[:8],
        "palabras",
        m["palabras"],
        "comparaciones",
        m["comparaciones"],
        [a["comparaciones"] for a in m["por_acto"]],
        "cortadas%",
        m["oraciones_cortadas_pct"],
        "diálogo",
        m["dialogo"],
        "clichés",
        m["cliches"],
        "frases",
        m["frases_640"],
    )
    print("   ", m["comparaciones_detalle"])
