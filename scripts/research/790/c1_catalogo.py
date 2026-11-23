"""Spike C1 (Spec-790 §2.11, §10.0): el catálogo de Yael. Mide las miniaturas del canal.

Etapas (cada una guarda en `c1/salidas/` y se puede repetir sola):
  ocr      Texto: máscaras de color (blanco y acento rojo/naranja) → Tesseract `spa` (psm 11)
           sobre cada máscara y sobre el gris → palabras con caja; se agrupan en líneas y en el
           bloque del título. Acento = palabras cuyo trazo es de color.
  figura   BiRefNet (el de E2) sobre la miniatura con el texto tapado de negro → caja de la
           figura (alto, centro, si la corta el borde de abajo, área).
  medir    Junta todo en `medidas.json` y etiqueta cada miniatura con reglas legibles
           (lado del título, alturas, tamaño de la figura) → plantilla.
  hojas    Una hoja por plantilla (recientes), con las cajas dibujadas.

    uv run python c1_catalogo.py [ocr|figura|medir|hojas|todo]
Solo Pillow (sin numpy). Tesseract con `insumos/tessdata` (spa).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import AQUI, Comfy  # noqa: E402
from e2_recortar import grafo_birefnet  # noqa: E402

CANAL = AQUI / "insumos" / "canal_yt"
SALIDAS = AQUI / "c1" / "salidas"
TESSDATA = AQUI / "insumos" / "tessdata"
RECIENTES = 36  # D19: desde junio de 2026 (la #36 es del 19/6; la #37, del 22/5: un mes sin videos)


def ids() -> list[str]:
    return [line.strip() for line in (CANAL / "ids.txt").read_text().splitlines() if line.strip()]


def fechas() -> dict[str, str]:
    meta = CANAL / "meta.txt"
    if not meta.exists():
        return {}
    out = {}
    for line in meta.read_text().splitlines():
        partes = line.split("|", 3)
        if len(partes) >= 2:
            out[partes[0]] = partes[1]
    return out


# ── texto ───────────────────────────────────────────────────────────────────────
def mascaras_de_texto(im: Image.Image) -> dict[str, Image.Image]:
    """Texto en negro sobre blanco (lo que lee mejor Tesseract)."""
    h, s, v = im.convert("HSV").split()
    blanco = ImageChops.multiply(v.point(lambda x: 255 if x > 185 else 0), s.point(lambda x: 255 if x < 60 else 0))
    rojo = h.point(lambda x: 255 if (x < 28 or x > 238) else 0)
    acento = ImageChops.multiply(
        ImageChops.multiply(rojo, s.point(lambda x: 255 if x > 120 else 0)),
        v.point(lambda x: 255 if x > 110 else 0),
    )
    return {
        "blanco": ImageChops.invert(blanco),
        "acento": ImageChops.invert(acento),
        "gris": im.convert("L"),
    }


def tesseract(img: Image.Image, tmp: Path) -> list[dict]:
    img.save(tmp)
    env = dict(os.environ, TESSDATA_PREFIX=str(TESSDATA))
    out = subprocess.run(
        ["tesseract", str(tmp), "-", "-l", "spa", "--psm", "11", "-c", "tessedit_create_tsv=1"],
        capture_output=True, text=True, env=env,
    ).stdout
    palabras = []
    for line in out.splitlines()[1:]:
        c = line.split("\t")
        if len(c) != 12 or not c[11].strip():
            continue
        texto = c[11].strip().strip("“”\"'|.,:;»«()¿?¡!-—")
        x, y, w, hh, conf = int(c[6]), int(c[7]), int(c[8]), int(c[9]), float(c[10])
        if conf < 60 or hh < 18 or len(texto) < 1:
            continue
        if not any(ch.isalnum() for ch in texto) or (len(texto) == 1 and not texto.isdigit() and texto not in "AYOE"):
            continue
        palabras.append({"t": texto, "caja": [x, y, x + w, y + hh], "conf": round(conf, 1)})
    return palabras


def iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area if area else 0


def fraccion(m: Image.Image, caja) -> float:
    """Fracción de píxeles «encendidos» (negros en la máscara invertida) dentro de la caja."""
    r = m.crop(caja).point(lambda x: 255 if x < 128 else 0)
    hist = r.histogram()
    total = sum(hist)
    return hist[255] / total if total else 0


def ocr(i: str) -> dict:
    im = Image.open(CANAL / f"{i}.jpg").convert("RGB")
    if im.size != (1280, 720):
        im = im.resize((1280, 720))
    ms = mascaras_de_texto(im)
    tmp = SALIDAS / "tmp.png"
    todas: list[dict] = []
    for nombre, m in ms.items():
        for p in tesseract(m, tmp):
            p["de"] = nombre
            todas.append(p)
    # sin duplicados: se queda la de más confianza
    todas.sort(key=lambda p: -p["conf"])
    palabras: list[dict] = []
    for p in todas:
        if all(iou(p["caja"], q["caja"]) < 0.3 for q in palabras):
            palabras.append(p)
    for p in palabras:
        fa, fb = fraccion(ms["acento"], p["caja"]), fraccion(ms["blanco"], p["caja"])
        p["acento"] = fa > 0.08 and fa > fb
    # ruido: fichas cortas con poca confianza (pedazos de la figura)
    palabras = [p for p in palabras if len(p["t"]) >= 3 or p["t"].isdigit() or p["conf"] >= 85]
    # líneas: por centro vertical y alto parecido; dentro de la línea, cortar si hay un hueco grande
    palabras.sort(key=lambda p: (p["caja"][1] + p["caja"][3]) / 2)
    filas: list[list[dict]] = []
    for p in palabras:
        cy, hh = (p["caja"][1] + p["caja"][3]) / 2, p["caja"][3] - p["caja"][1]
        for fila in filas:
            fcy = sum((q["caja"][1] + q["caja"][3]) / 2 for q in fila) / len(fila)
            fh = max(q["caja"][3] - q["caja"][1] for q in fila)
            if abs(cy - fcy) < 0.4 * max(hh, fh):
                fila.append(p)
                break
        else:
            filas.append([p])
    lineas: list[list[dict]] = []
    for fila in filas:
        fila.sort(key=lambda p: p["caja"][0])
        actual = [fila[0]]
        for p in fila[1:]:
            hh = max(q["caja"][3] - q["caja"][1] for q in actual + [p])
            if p["caja"][0] - actual[-1]["caja"][2] > 2.0 * hh:
                lineas.append(actual)
                actual = [p]
            else:
                actual.append(p)
        lineas.append(actual)
    lin = []
    for ln in lineas:
        ln.sort(key=lambda p: p["caja"][0])
        caja = [min(p["caja"][0] for p in ln), min(p["caja"][1] for p in ln),
                max(p["caja"][2] for p in ln), max(p["caja"][3] for p in ln)]
        lin.append({"texto": " ".join(p["t"] for p in ln), "caja": caja,
                    "alto": max(p["caja"][3] - p["caja"][1] for p in ln),
                    "acento": [p["t"] for p in ln if p["acento"]]})
    return {"palabras": palabras, "lineas": lin}


# ── la figura ─────────────────────────────────────────────────────────────────────
def tapar_texto(im: Image.Image, lineas: list[dict]) -> Image.Image:
    out = im.copy()
    d = ImageDraw.Draw(out)
    for ln in lineas:
        x0, y0, x1, y1 = ln["caja"]
        mg = round(0.25 * (y1 - y0))
        d.rectangle((x0 - mg, y0 - mg, x1 + mg, y1 + mg), fill=(0, 0, 0))
    return out


def caja_figura(m: Image.Image) -> dict | None:
    b = m.convert("L").resize((320, 180)).filter(ImageFilter.MedianFilter(5)).point(lambda x: 255 if x > 128 else 0)
    caja = b.getbbox()
    if not caja:
        return None
    hist = b.histogram()
    area = hist[255] / (320 * 180)
    x0, y0, x1, y1 = (v * 4 for v in caja)
    return {
        "caja": [x0, y0, x1, y1],
        "alto": round((y1 - y0) / 720, 3),
        "cx": round((x0 + x1) / 2 / 1280, 3),
        "cortada_abajo": y1 >= 712,
        "area": round(area, 3),
    }


async def figuras(lista: list[str], textos: dict) -> None:
    async with Comfy() as c:
        await c.liberar()
        for i in lista:
            destino = SALIDAS / f"{i}_figura.png"
            if destino.exists():
                continue
            im = Image.open(CANAL / f"{i}.jpg").convert("RGB").resize((1280, 720))
            tapado = SALIDAS / f"{i}_tapado.png"
            tapar_texto(im, textos[i]["lineas"]).save(tapado)
            sub = await c.subir(tapado)
            r = await c.correr(grafo_birefnet(sub, f"spec790/c1/{i}"))
            await c.bajar(r.imagenes[0], destino)
            print(i, r.segundos, flush=True)
        await c.liberar()


# ── etiquetas (reglas legibles) ─────────────────────────────────────────────────────
def etiquetar(t: dict, f: dict | None) -> dict:
    lineas = [ln for ln in t["lineas"] if ln["alto"] >= 24]
    if lineas:
        med = sorted(ln["alto"] for ln in lineas)[len(lineas) // 2]
        # una sola ficha corta solo vale si es el número gigante («3», «5»)
        lineas = [ln for ln in lineas
                  if len(ln["texto"].replace(" ", "")) >= 3 or (ln["texto"].strip().isdigit() and ln["alto"] > 1.3 * med)]
    if not lineas:
        return {"plantilla": "sin_titulo"}
    x0 = min(ln["caja"][0] for ln in lineas); x1 = max(ln["caja"][2] for ln in lineas)
    y0 = min(ln["caja"][1] for ln in lineas); y1 = max(ln["caja"][3] for ln in lineas)
    tcx, tcy = (x0 + x1) / 2 / 1280, (y0 + y1) / 2 / 720
    lado_t = "izquierda" if tcx < 0.42 else "derecha" if tcx > 0.58 else "centro"
    ys = sorted((ln["caja"][1] + ln["caja"][3]) / 2 / 720 for ln in lineas)
    saltos = [b - a for a, b in zip(ys, ys[1:])]
    dos_alturas = bool(saltos) and max(saltos) > 0.28
    altos = sorted((ln["alto"] for ln in lineas), reverse=True)
    out = {
        "titulo": {"caja": [x0, y0, x1, y1], "cx": round(tcx, 3), "cy": round(tcy, 3),
                   "ancho": round((x1 - x0) / 1280, 3), "alto": round((y1 - y0) / 720, 3),
                   "lineas": len(lineas), "linea_mayor": round(altos[0] / 720, 3),
                   "lado": lado_t, "dos_alturas": dos_alturas,
                   "acento": [w for ln in lineas for w in ln["acento"]]},
    }
    if f:
        out["figura"] = f
        lado_f = "izquierda" if f["cx"] < 0.45 else "derecha" if f["cx"] > 0.55 else "centro"
        tam = "primer_plano" if f["area"] > 0.30 else "chica" if f["alto"] < 0.5 else "grande"
        out["figura"]["lado"] = lado_f
        out["figura"]["tamano"] = tam
    else:
        lado_f, tam = "?", "sin_figura"
    if dos_alturas:
        p = "D_dos_alturas"
    elif lado_t == "centro":
        p = "E_titulo_centro"
    elif tam == "primer_plano":
        p = "C_primer_plano"
    elif tam == "chica":
        p = "B_lugar_manda"
    else:
        p = "A_figura_y_titulo"
    out["plantilla"] = p
    return out


def medir() -> dict:
    fs = fechas()
    textos = json.loads((SALIDAS / "textos.json").read_text())
    medidas = {}
    for n, i in enumerate(ids()):
        fp = SALIDAS / f"{i}_figura.png"
        f = caja_figura(Image.open(fp)) if fp.exists() else None
        medidas[i] = {"orden": n + 1, "fecha": fs.get(i), "reciente": n < RECIENTES,
                      **etiquetar(textos[i], f)}
    (SALIDAS / "medidas.json").write_text(json.dumps(medidas, indent=2, ensure_ascii=False))
    return medidas


def hojas(medidas: dict) -> None:
    grupos: dict[str, list[str]] = {}
    for i, m in medidas.items():
        if m["reciente"]:
            grupos.setdefault(m["plantilla"], []).append(i)
    W, H, C = 480, 270, 4
    for p, lista in grupos.items():
        R = (len(lista) + C - 1) // C
        o = Image.new("RGB", (C * W, R * H + 30), (25, 25, 25))
        d = ImageDraw.Draw(o)
        d.text((8, 8), f"{p}: {len(lista)} de las {RECIENTES} recientes", fill=(255, 255, 0))
        for k, i in enumerate(lista):
            im = Image.open(CANAL / f"{i}.jpg").convert("RGB").resize((1280, 720))
            dd = ImageDraw.Draw(im)
            m = medidas[i]
            if "titulo" in m:
                dd.rectangle(m["titulo"]["caja"], outline=(0, 160, 255), width=6)
            if "figura" in m:
                dd.rectangle(m["figura"]["caja"], outline=(255, 40, 40), width=6)
            x, y = (k % C) * W, 30 + (k // C) * H
            o.paste(im.resize((W - 6, H - 6)), (x + 3, y + 3))
            d.text((x + 8, y + 8), f"#{m['orden']}", fill=(255, 255, 0))
        o.save(SALIDAS / f"hoja_{p}.jpg", quality=85)
        print(SALIDAS / f"hoja_{p}.jpg")


if __name__ == "__main__":
    etapa = sys.argv[1] if len(sys.argv) > 1 else "todo"
    SALIDAS.mkdir(parents=True, exist_ok=True)
    if etapa in ("ocr", "todo"):
        textos = {}
        for n, i in enumerate(ids()):
            textos[i] = ocr(i)
            print(n + 1, i, " / ".join(ln["texto"] for ln in textos[i]["lineas"])[:110], flush=True)
        (SALIDAS / "textos.json").write_text(json.dumps(textos, indent=2, ensure_ascii=False))
    if etapa in ("figura", "todo"):
        textos = json.loads((SALIDAS / "textos.json").read_text())
        asyncio.run(figuras(ids(), textos))
    if etapa in ("medir", "hojas", "todo"):
        hojas(medir())
