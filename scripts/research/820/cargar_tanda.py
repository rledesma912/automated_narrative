"""Spec-820: carga una carpeta con <plantilla>.jpg como tanda nueva de Peter en dev (respalda el registro)."""

import datetime
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ID = "598a3b1d-75ff-4e6b-bae4-4db465468fbf"
PLANTILLAS = ["A_der", "A_izq", "C_primer_plano", "B_lugar"]
origen, n, nota = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
destino = Path(f"data/dev/miniaturas/{ID}/tanda_{n}")
destino.mkdir(parents=True, exist_ok=True)
for t in PLANTILLAS:
    shutil.copy(origen / f"{t}.jpg", destino / f"{t}.jpg")
c = sqlite3.connect("data/dev/stories.db")
raw = c.execute("select data from thumbnail where story_id=?", (ID,)).fetchone()[0]
Path(origen / f"respaldo_antes_tanda_{n}.json").write_text(raw)
d = json.loads(raw)
d["batches"] = [b for b in d["batches"] if b["n"] != n] + [
    {
        "n": n,
        "seed": 820,
        "color": "desaturado",
        "tone": "gris_frio",
        "seconds": 0.0,
        "images": [
            {"template": t, "file": f"tanda_{n}/{t}.jpg", "fused": True} for t in PLANTILLAS
        ],
        "created_at": datetime.datetime.now().astimezone().isoformat(),
        "nota": nota,
    }
]
c.execute("update thumbnail set data=? where story_id=?", (json.dumps(d, ensure_ascii=False), ID))
c.commit()
print("tanda", n, "cargada")
