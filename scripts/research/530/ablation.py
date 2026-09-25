# ruff: noqa — script de investigación de la Spec-530, se conserva tal como se corrió.
import re
import sqlite3
import statistics as st

import httpx

c = sqlite3.connect("prod_copy.db")
SID = "4a4d8cab-178f-460c-ae46-9e6e067638fb"
prompts = {
    n: c.execute(
        "select system_prompt,user_prompt from macro_beat where story_id=? and number=?", (SID, n)
    ).fetchone()
    for n in (2, 4)
}
PERFIL_RE = re.compile(r"== Perfil del Narrador ==.*", re.S)


def actual(s):
    return s


def minimo(s):
    s = PERFIL_RE.sub("", s)
    s = s.replace(
        "(Primera persona en pasado. Narrador: José. Tono: dramático. Registro: coloquial: Natural y diario.)",
        "(primera persona, pasado, registro coloquial)",
    )
    return s.replace(
        "Atmósfera: paranormal (fantasmas) - constante", "Atmósfera: paranormal (fantasmas)"
    )


def opuesto(s):
    s = PERFIL_RE.sub(
        """== Perfil del Narrador ==
Percepción: confiable: Ve y oye todo con total claridad (Distorsión: nula: Ninguna)
Voz: primera, pasado, poético
Registro: formal: Culto y literario, alta: Abundantes metáforas y comparaciones
Estilo Interpretativo: sobrenatural: Cree en fantasmas y lo explica todo por el más allá
Enfoque/Sesgos: miedo → perdida: Perder a un ser querido | atención → olores: Olores y texturas""",
        s,
    )
    s = s.replace(
        "Tono: dramático. Registro: coloquial: Natural y diario.",
        "Tono: poético. Registro: formal: Culto y literario.",
    )
    return s.replace("- constante", "- creciente")


V = {"actual": actual, "minimo": minimo, "opuesto": opuesto}
M = {
    "simil/100p": r"\bcomo (si|un|una|el|la|los|las)\b",
    "racional": r"cansancio|imaginaci|reflejo|explicaci|l[oó]gic|seguro que|deb[ií]a? (de )?ser|me dije",
    "sobrenat": r"esp[ií]ritu|alma|fantasma|m[aá]s all[aá]|aparici|[aá]nima|muert[ao]s? que",
    "sonido": r"sonido|ruido|zumbid|susurr|cruj|chirri|eco\b|silenci",
    "sombra": r"sombra|oscur|penumbra|tiniebl",
    "olor/text": r"\bolor|aroma|ol[ií]a|textur|[aá]sper|pegajos|h[uú]med",
    "voseo": r"\bvos\b|\bche\b|boludo|viste\b|\bsab[eé]s\b",
}
res = {}
for n, (sysp, user) in prompts.items():
    for v, f in V.items():
        for i in range(3):
            r = httpx.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "gemma3:12b",
                    "stream": False,
                    "options": {"temperature": 0.6, "num_ctx": 8192, "num_predict": 1000},
                    "messages": [
                        {"role": "system", "content": f(sysp)},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=900,
            )
            t = r.json()["message"]["content"]
            open(f"abl_{n}_{v}_{i}.txt", "w").write(t)
            w = len(t.split())
            sents = [x for x in re.split(r"[.!?…]+", t) if x.strip()]
            row = {"palabras": w, "pal/frase": w / max(1, len(sents))}
            for k, p in M.items():
                row[k] = len(re.findall(p, t, re.I)) * 100 / w
            res.setdefault((n, v), []).append(row)
            print(n, v, i, {k: round(x, 1) for k, x in row.items()}, flush=True)
print("\nPROMEDIOS (por 100 palabras salvo palabras y pal/frase)")
keys = list(next(iter(res.values()))[0])
print(f"{'acto/variante':16}" + "".join(f"{k:>11}" for k in keys))
for (n, v), rows in res.items():
    print(f"{f'{n}/{v}':16}" + "".join(f"{st.mean(r[k] for r in rows):11.1f}" for k in keys))
