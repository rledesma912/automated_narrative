"""Spike C2 (Spec-790 §2.11, §10.0): el título a la Yael.

Entra el gancho en texto plano («NUNCA DEBIMOS DEJARLOS ENTRAR»). Sale el título por niveles,
en la notación de `c2/ganchos.yaml`: líneas como las cortaría Yael, ~palabra = chica, *palabra =
acento, «3» al principio = número gigante.

  reglas   Python: palabras de enlace chicas, acento = la última palabra fuerte, cortes que
           equilibran el ancho y dejan el acento solo en su línea
  qwen     qwen2.5:14b local (Ollama), con los otros ganchos de Yael como ejemplos (deja uno
           afuera: el que se evalúa) y salida JSON
  gemma    gemma3:12b local, igual

Mide contra lo que hizo Yael (#1–24 de ago–nov): cortes exactos, cantidad de líneas, acento y
palabras chicas. Dibuja con Pillow y la Noto Serif SC ExtraBold una hoja: real | reglas | IA.

    uv run python c2_titulo.py [--metodos reglas,qwen,gemma] [--solo-hoja]
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import httpx
import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI  # noqa: E402

RAIZ = AQUI.parents[2]
FUENTE = RAIZ / "assets" / "fonts" / "NotoSerifSC-ExtraBold.ttf"
CANAL = AQUI / "insumos" / "canal_yt"
SALIDAS = AQUI / "c2" / "salidas"
OLLAMA = "http://localhost:11434"
MODELOS = {"qwen": "qwen2.5:14b", "gemma": "gemma3:12b"}

CHICAS = {"DE", "DEL", "EL", "LA", "LAS", "LOS", "AL", "EN", "CON", "A", "Y", "MI", "ME", "SU",
          "SI", "TE", "LO", "POR", "UN", "UNA", "SE"}
NARANJA = (255, 106, 26)


# ── notación ─────────────────────────────────────────────────────────────────────
def palabras(linea: str) -> list[dict]:
    out = []
    for t in linea.split():
        out.append({"t": t.lstrip("~*"), "chica": t.startswith("~"), "acento": t.startswith("*")})
    return out


def plano(lineas: list[str]) -> str:
    return " ".join(p["t"] for ln in lineas for p in palabras(ln))


def cortes(lineas: list[str]) -> list[str]:
    return [" ".join(p["t"] for p in palabras(ln)) for ln in lineas]


# ── reglas ───────────────────────────────────────────────────────────────────────
def ancho(ws: list[dict]) -> float:
    return sum(len(w["t"]) * (0.55 if w["chica"] else 1.0) for w in ws) + 0.6 * (len(ws) - 1)


def reglas(gancho: str) -> list[str]:
    toks = gancho.upper().split()
    numero = toks[0] if toks and toks[0].isdigit() else None
    resto = toks[1:] if numero else toks
    ws = [{"t": t, "chica": t.strip(",.") in CHICAS, "acento": False} for t in resto]
    fuertes = [i for i, w in enumerate(ws) if not w["chica"]]
    if fuertes:
        ws[fuertes[-1]]["acento"] = True
    mejor, costo_min = None, 1e9
    n = len(ws)
    for k in range(0, n):
        for cuts in itertools.combinations(range(1, n), k):
            bordes = [0, *cuts, n]
            ls = [ws[a:b] for a, b in zip(bordes, bordes[1:])]
            anchos = [ancho(ln) for ln in ls]
            costo = 3.0 * sum(max(0, a - 11) for a in anchos)  # cada línea entra en ~11 letras
            media = sum(anchos) / len(anchos)
            costo += 0.08 * sum((a - media) ** 2 for a in anchos) / len(anchos)
            costo += 0.6 * len(ls)  # pocas líneas…
            if len(ls) < 3 and n >= 3:
                costo += 2.0  # …pero Yael apila: de 3 a 4 líneas
            for ln in ls:
                if any(w["acento"] for w in ln) and len(ln) > 1:
                    costo += 1.5  # el acento va solo en su línea
                if len(ln) == 1 and ln[0]["chica"]:
                    costo += 1.0  # una chica sola en una línea, solo si no queda otra
            if costo < costo_min:
                mejor, costo_min = ls, costo
    lineas = []
    for ln in mejor or []:
        solo = len(ln) == 1
        lineas.append(" ".join(("*" if w["acento"] else "~" if w["chica"] and not solo else "") + w["t"] for w in ln))
    if numero:  # pegado a la primera línea (abarca dos), como en #7, #9, #10; con 2 líneas o menos,
        # solo arriba (#5): así el bloque gana alto y no ancho
        lineas = [numero] + lineas if len(lineas) <= 2 else [f"{numero} {lineas[0]}"] + lineas[1:]
    return lineas


# ── IA local ─────────────────────────────────────────────────────────────────────
INSTRUCCION = """Sos la diseñadora de las miniaturas de un canal de relatos de terror. Armás el título de la miniatura a partir de una frase.
Reglas de la notación:
- cada elemento de "lineas" es una línea del título, como la cortarías vos (líneas cortas, de 1 a 3 palabras);
- ~PALABRA = palabra chica (más o menos la mitad del tamaño): las de enlace como DE, EL, LA, CON, EN;
- *PALABRA = palabra en color de acento (naranja): la palabra que más asusta o la clave, casi siempre una sola;
- un número al principio («3», «5») va gigante.
Usá exactamente las mismas palabras de la frase, en el mismo orden, en mayúsculas. No agregues ni quites palabras.
Estos son títulos tuyos:
{ejemplos}
Respondé solo con el JSON."""


def ia(modelo: str, gancho: str, ejemplos: list[dict]) -> tuple[list[str], float]:
    ej = "\n".join(
        f'Frase: {plano(e["lineas"])}\n{json.dumps({"lineas": e["lineas"]}, ensure_ascii=False)}' for e in ejemplos
    )
    esquema = {"type": "object", "properties": {"lineas": {"type": "array", "items": {"type": "string"}}},
               "required": ["lineas"]}
    t0 = time.time()
    r = httpx.post(f"{OLLAMA}/api/chat", timeout=300, json={
        "model": modelo, "stream": False, "format": esquema, "options": {"temperature": 0.2},
        "messages": [{"role": "system", "content": INSTRUCCION.format(ejemplos=ej)},
                     {"role": "user", "content": f"Frase: {gancho}"}],
    })
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])["lineas"], round(time.time() - t0, 1)


# ── medir ────────────────────────────────────────────────────────────────────────
def comparar(real: list[str], prop: list[str]) -> dict:
    pr, pp = [p for ln in real for p in palabras(ln)], [p for ln in prop for p in palabras(ln)]
    mismas = [p["t"] for p in pr] == [p["t"].upper() for p in pp]
    out = {"mismas_palabras": mismas, "cortes_exactos": cortes(real) == [c.upper() for c in cortes(prop)],
           "lineas_real": len(real), "lineas_prop": len(prop)}
    if mismas:
        ar = {i for i, p in enumerate(pr) if p["acento"]}
        ap = {i for i, p in enumerate(pp) if p["acento"]}
        out["acento_real"] = bool(ar)
        out["acento_igual"] = ar == ap
        out["acento_toca"] = bool(ar & ap) if ar else None
        cr = {i for i, p in enumerate(pr) if p["chica"]}
        cp = {i for i, p in enumerate(pp) if p["chica"]}
        out["chicas"] = (len(cr & cp), len(cr), len(cp))
    return out


def resumen(res: list[dict]) -> dict:
    n = len(res)
    ok = [r for r in res if r["mismas_palabras"]]
    con_acento = [r for r in ok if r["acento_real"]]
    tp = sum(r["chicas"][0] for r in ok); real = sum(r["chicas"][1] for r in ok); prop = sum(r["chicas"][2] for r in ok)
    return {
        "n": n,
        "mismas_palabras": f"{len(ok)}/{n}",
        "cortes_exactos": f"{sum(r['cortes_exactos'] for r in res)}/{n}",
        "lineas_iguales": f"{sum(r['lineas_real'] == r['lineas_prop'] for r in res)}/{n}",
        "lineas_±1": f"{sum(abs(r['lineas_real'] - r['lineas_prop']) <= 1 for r in res)}/{n}",
        "acento_toca (con acento real)": f"{sum(bool(r['acento_toca']) for r in con_acento)}/{len(con_acento)}",
        "chicas_precision": round(tp / prop, 2) if prop else None,
        "chicas_recall": round(tp / real, 2) if real else None,
    }


# ── dibujar ──────────────────────────────────────────────────────────────────────
def medir_ancho(lineas: list[str], G: int) -> float:
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    f_g = ImageFont.truetype(str(FUENTE), G)
    f_c = ImageFont.truetype(str(FUENTE), round(G * 0.55))
    f_n = ImageFont.truetype(str(FUENTE), round(G * 2.0))
    mayor = 0.0
    for k, ln in enumerate(lineas):
        toks = ln.split()
        extra = 0.0
        if k == 0 and toks and toks[0].lstrip("*").isdigit() and len(toks) > 1:
            extra = d.textlength(toks[0].lstrip("*"), font=f_n) + 8
            ln = " ".join(toks[1:])
        w = sum(d.textlength(p["t"] + " ", font=f_c if p["chica"] else f_g) - (2 if p["chica"] else 4) for p in palabras(ln))
        mayor = max(mayor, w + extra, (w + extra) if k < 2 else 0)
    return mayor


def dibujar(lineas: list[str], ancho_c: int = 620, alto_c: int = 560, G: int | None = None,
            alinear: str = "izquierda") -> Image.Image:
    """El bloque del título en el estilo del canal: serif blanca, chicas al 55 %, acento naranja con
    brillo, número gigante, sombra negra difusa. Alineado a la izquierda. El tamaño se ajusta para
    que la línea más ancha entre en el bloque y el alto también."""
    if G is None:
        G = 170
        while G > 30 and (medir_ancho(lineas, G) > ancho_c - 40 or len(lineas) * G * 0.98 + 40 > alto_c):
            G -= 2
    lienzo = Image.new("RGBA", (ancho_c, alto_c), (0, 0, 0, 0))
    capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    f_g = ImageFont.truetype(str(FUENTE), G)
    f_c = ImageFont.truetype(str(FUENTE), round(G * 0.55))
    f_n = ImageFont.truetype(str(FUENTE), round(G * 2.0))
    y, x0 = 20, 20
    ls = list(lineas)
    numero_al_lado = None
    if ls and ls[0].split()[0].lstrip("*").isdigit() and len(ls[0].split()) > 1:
        tok = ls[0].split()[0]
        numero_al_lado = (tok.lstrip("*"), tok.startswith("*"))
        ls[0] = " ".join(ls[0].split()[1:])
    def ancho_linea(ln: str) -> float:
        if ln.strip().lstrip("*").isdigit():
            return d.textlength(ln.strip().lstrip("*"), font=f_n)
        return sum(d.textlength(p["t"] + " ", font=f_c if p["chica"] else f_g) - (2 if p["chica"] else 4)
                   for p in palabras(ln)) - d.textlength(" ", font=f_g) + 4

    derecha = ancho_c - 20
    xi = x0
    ancho_num = 0.0
    if numero_al_lado:
        t, acento = numero_al_lado
        ancho_num = d.textlength(t, font=f_n) + 8
        if alinear == "derecha":
            xn = derecha - max(ancho_linea(ln) for ln in ls[:2]) - ancho_num
        else:
            xn = x0
        d.text((xn, y - 0.25 * G), t, font=f_n, fill=NARANJA if acento else (255, 255, 255))
        xi = x0 + ancho_num
    for k, ln in enumerate(ls):
        x = xi if (numero_al_lado and k < 2) else x0
        if alinear == "derecha":
            x = derecha - ancho_linea(ln)
        if ln.strip().lstrip("*").isdigit():
            d.text((x, y - 0.3 * G), ln.strip().lstrip("*"), font=f_n, fill=NARANJA if ln.startswith("*") else (255, 255, 255))
            y += round(1.75 * G)
            continue
        for p in palabras(ln):
            f = f_c if p["chica"] else f_g
            dy = round(G * 0.36) if p["chica"] else 0  # las chicas apoyadas en la línea de base
            d.text((x, y + dy), p["t"], font=f, fill=NARANJA if p["acento"] else (255, 255, 255))
            x += d.textlength(p["t"] + " ", font=f) - (2 if p["chica"] else 4)
        y += round(G * 0.98)
    alfa = capa.getchannel("A")
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    sombra.putalpha(alfa.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(8)))
    lienzo = Image.alpha_composite(lienzo, sombra)
    # brillo del acento: el naranja, difuminado
    r, g, b, a = capa.split()
    naranja = Image.eval(r, lambda v: 255 if v > 200 else 0)
    mask_acento = Image.composite(a, Image.new("L", a.size, 0), Image.eval(b, lambda v: 255 if v < 80 else 0))
    brillo = Image.new("RGBA", lienzo.size, NARANJA + (0,))
    brillo.putalpha(mask_acento.filter(ImageFilter.GaussianBlur(10)).point(lambda v: v * 0.8))
    del naranja
    lienzo = Image.alpha_composite(lienzo, brillo)
    return Image.alpha_composite(lienzo, capa)


def hoja(gt: list[dict], props: dict[str, dict[int, list[str]]]) -> Path:
    ids = [line.strip() for line in (CANAL / "ids.txt").read_text().splitlines()]
    cols = ["real"] + list(props)
    W, H = 420, 236
    filas = gt
    o = Image.new("RGB", (W * len(cols), H * len(filas) + 30), (18, 18, 18))
    d = ImageDraw.Draw(o)
    for c, nombre in enumerate(cols):
        d.text((c * W + 8, 8), nombre, fill=(255, 255, 0))
    for r, e in enumerate(filas):
        y = 30 + r * H
        real = Image.open(CANAL / f"{ids[e['n'] - 1]}.jpg").convert("RGB").resize((W - 6, H - 6))
        o.paste(real, (3, y + 3))
        d.text((8, y + 6), f"#{e['n']}", fill=(255, 255, 0))
        for c, nombre in enumerate(props, start=1):
            lin = props[nombre].get(e["n"])
            if not lin:
                continue
            fondo = Image.new("RGBA", (620, 560), (28, 28, 34, 255))
            bloque = Image.alpha_composite(fondo, dibujar(lin)).convert("RGB")
            bloque.thumbnail((W - 6, H - 6))
            o.paste(bloque, (c * W + 3, y + 3))
    destino = SALIDAS / "hoja_titulos.jpg"
    o.save(destino, quality=88)
    return destino


def main(metodos: list[str]) -> None:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    gt = yaml.safe_load((AQUI / "c2" / "ganchos.yaml").read_text())
    previo = SALIDAS / "propuestas.json"
    props: dict[str, dict] = json.loads(previo.read_text()) if previo.exists() else {}
    props = {m: {int(k): v for k, v in d.items()} for m, d in props.items()}
    tiempos: dict[str, list[float]] = {}
    for m in metodos:
        props[m] = {}
        for e in gt:
            g = plano(e["lineas"])
            if m == "reglas":
                props[m][e["n"]] = reglas(g)
            else:
                otros = [x for x in gt if x["n"] != e["n"]]
                try:
                    lin, s = ia(MODELOS[m], g, otros)
                except Exception as err:  # noqa: BLE001 (spike: se anota y sigue)
                    print(m, e["n"], "ERROR", err)
                    continue
                props[m][e["n"]] = lin
                tiempos.setdefault(m, []).append(s)
            print(m, e["n"], props[m][e["n"]], flush=True)
        if m != "reglas":
            httpx.post(f"{OLLAMA}/api/generate", json={"model": MODELOS[m], "keep_alive": 0})
    previo.write_text(json.dumps(props, ensure_ascii=False, indent=1))
    informe = {}
    for m, d in props.items():
        res = [comparar(e["lineas"], d[e["n"]]) for e in gt if e["n"] in d]
        informe[m] = resumen(res)
        if m in tiempos:
            informe[m]["segundos_medio"] = round(sum(tiempos[m]) / len(tiempos[m]), 1)
    (SALIDAS / "medidas.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2))
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    print(hoja(gt, props))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--metodos", default="reglas,qwen,gemma")
    ap.add_argument("--solo-hoja", action="store_true")
    a = ap.parse_args()
    main([] if a.solo_hoja else a.metodos.split(","))
