# ruff: noqa — script de investigación de la Spec-530, se conserva tal como se corrió.
import copy
import json

import yaml

st = yaml.safe_load(open("pena.yaml"))
esc = json.load(open("escaleta_1.json"))["actos"]
new = copy.deepcopy(st)
paras = [" ".join(h.rstrip(".") + "." for h in a["hechos"]) for a in esc]
new["sinopsis"] = "\n\n".join(paras)
for i, p in enumerate(paras, 1):
    new["storyteller_config"]["actos"][f"act_{i}"]["text"] = p
sc = new["storyteller_config"]["scenarios"]
sc += [
    {
        "id": "S3",
        "order": 3,
        "name": "La ruta de noche",
        "description": "Ruta de dos manos sin iluminación, curvas entre campos, banquinas de tierra.",
    },
    {
        "id": "S4",
        "order": 4,
        "name": "El pedestal al costado de la ruta",
        "description": "Un pequeño pedestal de piedra en la banquina, con una foto de una mujer y una placa con su nombre.",
    },
]
new["escenarios"] = "; ".join(f"{s['name']}: {s['description']}" for s in sc)
new["title"] = "la pena del colectivo (escaleta)"
yaml.safe_dump(new, open("pena_escaleta.yaml", "w"), allow_unicode=True, sort_keys=False)
print(new["sinopsis"])
