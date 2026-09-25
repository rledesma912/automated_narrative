# ruff: noqa — script de investigación de la Spec-530, se conserva tal como se corrió.
import json
import time

import httpx
import yaml

story = yaml.safe_load(open("pena.yaml"))
direccion = """- Qué historia: un chofer de micro nocturno que se cruza con el fantasma de una mujer que murió en su micro.
- Efecto buscado: pavor creciente, que se vuelve culpa y termina en un final melancólico.
- Final: INTENCIONAL — el alma de la mujer descansa en paz después de las flores. No convertirlo en un final de terror."""
respuestas = """- Meta de José esa noche: tiene que llegar a casa antes del amanecer; su hija está internada y le prometió estar a la mañana.
- Agencia: la primera vez limpia el espejo convencido de que es un reflejo; en la terminal le pregunta al sereno por la mujer que murió en el micro.
- Escalada: primero un olor a flores dentro del micro vacío; después la mujer en distintos asientos por el espejo; después el toque en el hombro; después en la cara (esto último provoca que pierda el control).
- En juego: si choca, pierde el trabajo y no llega con su hija.
- Historia secreta: José manejaba el micro la noche que la mujer se descompensó; ella le pidió que parara y él siguió para no atrasarse. Nunca se lo contó a nadie.
- Siembra y cosecha: en el acto 1 recuerda de pasada a una pasajera con un ramo de flores que pidió bajar; en el acto 4 la foto del pedestal la muestra con ese ramo."""
esc = [s["name"] for s in story["storyteller_config"]["scenarios"]]
schema = {
    "type": "object",
    "properties": {
        "actos": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "numero": {"type": "integer"},
                    "objetivo_jose": {"type": "string"},
                    "hechos": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 5,
                        "items": {"type": "string"},
                    },
                    "cambio": {
                        "type": "object",
                        "properties": {"de": {"type": "string"}, "a": {"type": "string"}},
                        "required": ["de", "a"],
                    },
                    "motivo_nuevo": {"type": "string"},
                    "escenario": {"type": "string"},
                    "no_revelar_todavia": {"type": "string"},
                },
                "required": [
                    "numero",
                    "objetivo_jose",
                    "hechos",
                    "cambio",
                    "motivo_nuevo",
                    "escenario",
                    "no_revelar_todavia",
                ],
            },
        }
    },
    "required": ["actos"],
}
prompt = f"""Sos el editor que arma la ESCALETA de un cuento de terror en 5 actos (se genera después automáticamente y se escucha como audio).
Actos: 1 exposición, 2 acción ascendente, 3 clímax, 4 acción descendente, 5 desenlace breve.

DIRECCIÓN DEL AUTOR (manda sobre todo lo demás):
{direccion}

SINOPSIS ORIGINAL DEL AUTOR (sus hechos se respetan, no se contradicen):
{story["sinopsis"]}

DECISIONES QUE EL AUTOR TOMÓ AL RESPONDER PREGUNTAS (hay que integrarlas todas):
{respuestas}

ESCENARIOS DISPONIBLES: {"; ".join(esc)}. Si un acto ocurre en otro lugar, escribí "nuevo: <nombre>: <descripción breve>".

Para cada acto devolvé:
- objetivo_jose: qué quiere o intenta José en ese acto (una frase).
- hechos: 3 a 5 hechos CONCRETOS y en orden, en tercera persona, con acciones de José (no sensaciones sueltas). Cada hecho ocurre una sola vez en todo el cuento: ningún acto repite un hecho de otro.
- cambio: cómo está la situación de José al empezar ("de") y al terminar ("a"); tienen que ser distintos.
- motivo_nuevo: la imagen o detalle sensorial que aparece por primera vez en este acto (distinto en cada acto).
- escenario: dónde ocurre.
- no_revelar_todavia: qué información se guarda para un acto posterior ("nada" en el acto 5).
Español rioplatense, frases simples."""
for run in (1, 2):
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
    json.dump(out, open(f"escaleta_{run}.json", "w"), ensure_ascii=False, indent=1)
    print(f"\n######## escaleta {run}: {time.time() - t:.0f}s")
    for a in out["actos"]:
        print(
            f"\n[Acto {a['numero']}] {a['escenario']}\n  objetivo: {a['objetivo_jose']}\n  cambio: {a['cambio']['de']} → {a['cambio']['a']}\n  motivo nuevo: {a['motivo_nuevo']}\n  guarda: {a['no_revelar_todavia']}"
        )
        for h in a["hechos"]:
            print("   -", h)
