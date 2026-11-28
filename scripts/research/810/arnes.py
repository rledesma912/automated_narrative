"""El arnés de la calabaza que habla (Spec-810 §1b). Python orquesta; cada llamada a ComfyUI hace
una sola tarea (D15 de la 790): un tramo de audio → un clip.

  1. audio: mono 16 kHz, normalizado, cortado en tramos por las pausas (sin pasar `max_s`)
  2. imagen: el encuadre (horizontal o vertical) con la cabeza en el mismo lugar
  3. un clip por tramo (ComfyUI), semilla fija
  4. chequeos por clip (Python): la cabeza sigue igual, los ojos siguen oscuros con la pupila
     violeta, la boca se mueve cuando hay voz y se queda quieta en los silencios. Si no pasa,
     otra semilla (tope de reintentos)
  5. armar (ffmpeg): los tramos con un corte de cámara (plano y primer plano alternados) y
     siempre el audio original
  6. registro: corrida.json con todo lo de cada tramo

Sin numpy (como imagen.py de la 790): PIL, `wave`, `audioop`-free, ffmpeg por subprocess.
"""

from __future__ import annotations

import array
import json
import math
import subprocess
import sys
import time
import uuid
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx
import yaml
from PIL import Image, ImageChops, ImageFilter, ImageStat

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from src.infrastructure.adapters.comfy.client import ComfyClient, ComfyError, llenar  # noqa: E402

AQUI = Path(__file__).resolve().parent
FPS = 25
SR = 16000


# ── 1. audio ──────────────────────────────────────────────────────────────────────────────────


def a_wav16(origen: Path, destino: Path) -> Path:
    """Mono, 16 kHz, 16 bits, con el volumen normalizado (loudnorm)."""
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(origen),
            "-ac",
            "1",
            "-ar",
            str(SR),
            "-af",
            "loudnorm=I=-18:TP=-2",
            "-sample_fmt",
            "s16",
            str(destino),
        ],
        check=True,
    )
    return destino


def muestras(ruta: Path) -> array.array:
    with wave.open(str(ruta)) as w:
        datos = array.array("h", w.readframes(w.getnframes()))
    return datos


def energia(datos: array.array, ventana_s: float) -> list[float]:
    """RMS por ventana (0..1)."""
    n = max(1, round(SR * ventana_s))
    out = []
    for i in range(0, len(datos), n):
        b = datos[i : i + n]
        out.append(math.sqrt(sum(x * x for x in b) / max(1, len(b))) / 32768)
    return out


def tramos(datos: array.array, max_s: float, pausa_s: float = 0.25) -> list[tuple[float, float]]:
    """Cortes por las pausas: cada tramo termina en el silencio más tardío que entre en `max_s`.
    Si no hay pausa, se corta en `max_s`."""
    v = 0.05
    e = energia(datos, v)
    umbral = max(0.01, 0.12 * max(e))
    silencio = [x < umbral for x in e]
    # centro de cada pausa larga
    pausas, i = [], 0
    while i < len(silencio):
        if silencio[i]:
            j = i
            while j < len(silencio) and silencio[j]:
                j += 1
            if (j - i) * v >= pausa_s:
                pausas.append((i + j) / 2 * v)
            i = j
        else:
            i += 1
    total = len(datos) / SR
    cortes, inicio = [], 0.0
    while total - inicio > max_s:
        candidatas = [p for p in pausas if inicio + 1.0 < p <= inicio + max_s]
        fin = candidatas[-1] if candidatas else inicio + max_s
        cortes.append((inicio, fin))
        inicio = fin
    cortes.append((inicio, total))
    return cortes


def recortar_audio(origen: Path, desde: float, hasta: float, destino: Path) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(origen),
            "-ss",
            f"{desde:.3f}",
            "-to",
            f"{hasta:.3f}",
            "-c:a",
            "pcm_s16le",
            str(destino),
        ],
        check=True,
    )
    return destino


def cuadros_para(segundos: float) -> int:
    """Wan pide 4k + 1 cuadros."""
    k = math.ceil(segundos * FPS / 4)
    return 4 * k + 1


# ── 2. imagen ─────────────────────────────────────────────────────────────────────────────────


def _mascara_hue(im: Image.Image, h0: int, h1: int, s_min: int, v_min: int) -> Image.Image:
    h, s, v = im.convert("HSV").split()
    m = ImageChops.multiply(
        h.point(lambda x: 255 if h0 < x < h1 else 0), s.point(lambda x: 255 if x > s_min else 0)
    )
    return ImageChops.multiply(m, v.point(lambda x: 255 if x > v_min else 0))


def naranja(im):
    return _mascara_hue(im, 8, 32, 90, 50)


def violeta(im):
    return _mascara_hue(im, 175, 230, 60, 60)


def _denso(m: Image.Image, frac: float = 0.25) -> tuple[int, int, int, int]:
    """La caja donde la máscara es densa: filas y columnas con al menos `frac` del máximo
    (el cuero o un reflejo anaranjado sueltos no la estiran)."""
    w, h = m.size
    px = m.load()
    filas = [sum(1 for x in range(0, w, 2) if px[x, y]) for y in range(h)]
    cols = [sum(1 for y in range(0, h, 2) if px[x, y]) for x in range(w)]
    fy, fx = max(filas) * frac, max(cols) * frac
    ys = [y for y, n in enumerate(filas) if n >= fy]
    xs = [x for x, n in enumerate(cols) if n >= fx]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


@dataclass
class Zonas:
    cabeza: tuple[int, int, int, int]
    ojos: tuple[int, int, int, int]
    boca: tuple[int, int, int, int]


def zonas(im: Image.Image) -> Zonas:
    """La cabeza (lo naranja de arriba), los ojos (lo violeta) y la boca (el tercio de abajo
    de la cabeza), medidas sobre el cuadro ya encuadrado."""
    alto = im.height
    cal = naranja(im).filter(ImageFilter.MedianFilter(5))
    tapa = Image.new("L", im.size, 0)
    tapa.paste(255, (0, 0, im.width, int(alto * 0.75)))
    cal = ImageChops.multiply(cal, tapa)
    x0, y0, x1, y1 = _denso(cal)
    ojos = violeta(im).getbbox() or (x0, y0 + (y1 - y0) // 3, x1, y0 + (y1 - y0) // 2)
    m = 6
    ojos = (ojos[0] - m, ojos[1] - m, ojos[2] + m, ojos[3] + m)
    boca = (x0 + (x1 - x0) // 6, y0 + (y1 - y0) * 3 // 5, x1 - (x1 - x0) // 6, y1)
    return Zonas((x0, y0, x1, y1), ojos, boca)


def oscurecer_ojos(im: Image.Image, pupila: float = 0.7, nucleo: int = 200) -> Image.Image:
    """Los ojos de Yael (Spec-800 H1a): la cuenca negra y una pupila violeta tenue, solo dentro de
    la caja de los ojos (el reflejo violeta del auricular no cuenta). Sirve para cualquier pose."""
    from PIL import ImageEnhance

    z = zonas(im)
    caja = tuple(int(v) for v in z.ojos)

    def solo(m: Image.Image) -> Image.Image:
        out = Image.new("L", m.size, 0)
        out.paste(m.crop(caja), caja[:2])
        return out

    cuenca = (
        solo(violeta(im)).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(2.5))
    )
    centro = solo(_mascara_hue(im, 175, 230, 60, nucleo)).filter(ImageFilter.GaussianBlur(1.5))
    sal = Image.composite(ImageEnhance.Brightness(im).enhance(0.08), im, cuenca)
    return Image.composite(ImageEnhance.Brightness(im).enhance(pupila), sal, centro)


def encuadrar(base: Image.Image, ancho: int, alto: int, cabeza_rel: float = 0.42) -> Image.Image:
    """Recorta un cuadro ancho × alto donde la cabeza ocupa `cabeza_rel` del alto, centrada y
    arriba (a 1/8 del borde). Por el tamaño de la cabeza: las poses vienen a distintas distancias."""
    rect = encuadre_rect(base, ancho, alto, cabeza_rel)
    return base.crop(tuple(round(v) for v in rect)).resize((ancho, alto), Image.Resampling.LANCZOS)


def encuadre_rect(
    base: Image.Image, ancho: int, alto: int, cabeza_rel: float = 0.42
) -> tuple[float, float, float, float]:
    cab = zonas(base).cabeza
    cx = (cab[0] + cab[2]) / 2
    h = (cab[3] - cab[1]) / cabeza_rel
    w = h * ancho / alto
    if w > base.width:
        w = base.width
        h = w * alto / ancho
    if h > base.height:
        h = base.height
        w = h * ancho / alto
    top = min(max(0, cab[1] - h / 8), base.height - h)
    left = min(max(0, cx - w / 2), base.width - w)
    return (left, top, left + w, top + h)


def llevar(caja, rect, ancho: int, alto: int) -> tuple[float, float, float, float]:
    """Una caja de la imagen base al cuadro encuadrado (`rect` → ancho × alto)."""
    sx, sy = ancho / (rect[2] - rect[0]), alto / (rect[3] - rect[1])
    return (
        (caja[0] - rect[0]) * sx,
        (caja[1] - rect[1]) * sy,
        (caja[2] - rect[0]) * sx,
        (caja[3] - rect[1]) * sy,
    )


def seguir(
    cuadros: list[Image.Image], caja, radio: int = 24, escala: int = 2
) -> list[tuple[int, int]]:
    """Dónde se movió la caja en cada cuadro respecto del primero: busca el corrimiento que menos
    cambia el recorte (en gris y a media escala). Sigue por la imagen, no por el color."""

    def g(im):
        return (
            im.convert("L")
            .resize((im.width // escala, im.height // escala))
            .filter(ImageFilter.GaussianBlur(1))
        )

    x0, y0, x1, y1 = (round(v / escala) for v in caja)
    ref = g(cuadros[0]).crop((x0, y0, x1, y1))
    r = radio // escala
    out, (px, py) = [], (0, 0)
    for c in cuadros:
        gc = g(c)
        mejor = None
        for dy in range(py - r // 2, py + r // 2 + 1):
            for dx in range(px - r // 2, px + r // 2 + 1):
                d = ImageStat.Stat(
                    ImageChops.difference(ref, gc.crop((x0 + dx, y0 + dy, x1 + dx, y1 + dy)))
                ).mean[0]
                if mejor is None or d < mejor[0]:
                    mejor = (d, dx, dy)
        px, py = mejor[1], mejor[2]
        out.append((px * escala, py * escala))
    return out


# ── 3. ComfyUI (una llamada = un clip) ────────────────────────────────────────────────────────


class ClienteVideo(ComfyClient):
    """El cliente de la 790 con dos cosas más: sube cualquier archivo (audio) y baja la primera
    salida aunque sea video. Los workflows de este spike viven en `810/workflows/`."""

    def __init__(self, timeout: float = 3600):
        super().__init__(timeout=timeout)

    async def subir_archivo(self, ruta: Path) -> str:
        async with httpx.AsyncClient(base_url=self.url, timeout=120) as h:
            with ruta.open("rb") as f:
                r = await h.post(
                    "/upload/image",
                    files={
                        "image": (
                            f"{uuid.uuid4().hex[:8]}_{ruta.name}",
                            f,
                            "application/octet-stream",
                        )
                    },
                    data={"subfolder": "spec810", "overwrite": "true"},
                )
        r.raise_for_status()
        d = r.json()
        return f"{d['subfolder']}/{d['name']}" if d.get("subfolder") else d["name"]

    async def clip(
        self, receta: str, valores: dict, entradas: dict[str, Path], destino: Path
    ) -> dict:
        base = AQUI / "workflows" / receta
        grafo = json.loads((base / "workflow.api.json").read_text())
        params = yaml.safe_load((base / "params.yaml").read_text())["params"]
        for nombre, ruta in entradas.items():
            valores[nombre] = await self.subir_archivo(ruta)
        g = llenar(grafo, params, valores)
        inicio = time.monotonic()
        async with httpx.AsyncClient(base_url=self.url, timeout=60) as h:
            r = await h.post("/prompt", json={"prompt": g, "client_id": self.client_id})
        if r.status_code != 200:
            raise ComfyError(f"{receta}: el grafo no entra", r.text[:1500])
        pid = r.json()["prompt_id"]
        pico = 0.0
        while True:
            hist = (await self._get(f"/history/{pid}")).json().get(pid)
            try:
                libre = await self.vram_libre_mb()
                total = (await self._get("/system_stats", timeout=5)).json()["devices"][0][
                    "vram_total"
                ] / 2**20
                pico = max(pico, total - libre)
            except Exception:  # noqa: BLE001 — la medición no frena el clip
                pass
            if hist:
                st = hist.get("status", {})
                if st.get("status_str") == "error":
                    raise ComfyError(f"{receta}: falló", json.dumps(st)[:1500])
                if st.get("completed") or hist.get("outputs"):
                    break
            if time.monotonic() - inicio > self.timeout:
                await self.cancelar(pid)
                raise ComfyError(f"{receta}: tardó más de {self.timeout:.0f} s")
            await asyncio_sleep(2)
        segundos = time.monotonic() - inicio
        archivos = [
            a
            for out in hist.get("outputs", {}).values()
            for k, lista in out.items()
            if isinstance(lista, list)
            for a in lista
            if isinstance(a, dict) and "filename" in a
        ]
        if not archivos:
            raise ComfyError(f"{receta}: sin salida")
        a = archivos[0]
        r = await self._get(
            "/view",
            params={
                "filename": a["filename"],
                "subfolder": a.get("subfolder", ""),
                "type": a.get("type", "output"),
            },
        )
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        return {"segundos": round(segundos, 1), "vram_pico_mb": round(pico)}


async def asyncio_sleep(s: float) -> None:
    import asyncio

    await asyncio.sleep(s)


# ── 4. chequeos ───────────────────────────────────────────────────────────────────────────────


def cuadros_de(video: Path, carpeta: Path, fps: int = FPS) -> list[Path]:
    carpeta.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"fps={fps}",
            str(carpeta / "c_%04d.png"),
        ],
        check=True,
    )
    return sorted(carpeta.glob("c_*.png"))


def _dif(a: Image.Image, b: Image.Image) -> float:
    """Diferencia media 0..1 en gris, suavizada (no mide el grano, mide la forma)."""
    ga = a.convert("L").filter(ImageFilter.GaussianBlur(2))
    gb = b.convert("L").filter(ImageFilter.GaussianBlur(2))
    return ImageStat.Stat(ImageChops.difference(ga, gb)).mean[0] / 255


def _pearson(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n < 3:
        return 0.0
    x, y = x[:n], y[:n]
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / (sx * sy)


@dataclass
class Chequeo:
    cabeza_dif_max: (
        float  # cuánto se aleja la parte de arriba de la cabeza (ojos, tallo) del cuadro 1
    )
    ojos_violeta: float  # violeta en la zona de los ojos, relativo al cuadro de inicio (1 = igual)
    boca_voz: float  # correlación entre lo que se mueve la boca y la energía de la voz
    boca_mueve: float  # cuánto se mueve la boca con voz (media de la diferencia entre cuadros)
    pasa: bool
    motivos: list[str] = field(default_factory=list)


UMBRALES = {
    "cabeza_dif_max": 0.10,
    "ojos_min": 0.4,
    "ojos_max": 2.5,
    "boca_voz_min": 0.15,
    "boca_mueve_min": 0.004,
}


def chequear(video: Path, inicio: Image.Image, audio: Path, tmp: Path) -> Chequeo:
    cs = [Image.open(c).convert("RGB") for c in cuadros_de(video, tmp)]
    z = zonas(inicio)
    x0, y0, x1, y1 = z.cabeza
    arriba = (x0, y0, x1, y0 + (y1 - y0) // 2)  # ojos y frente: no tienen que cambiar
    ref_arriba = cs[0].crop(arriba)
    cab = max(_dif(ref_arriba, c.crop(arriba)) for c in cs)
    v0 = max(1, sum(violeta(inicio.crop(z.ojos)).histogram()[255:]))
    vs = [sum(violeta(c.crop(z.ojos)).histogram()[255:]) / v0 for c in cs]
    ojos = sorted(vs)[len(vs) // 2]
    boca = [_dif(cs[i - 1].crop(z.boca), cs[i].crop(z.boca)) for i in range(1, len(cs))]
    e = energia(muestras(audio), 1 / FPS)[1 : len(boca) + 1]
    voz = [m for m, en in zip(boca, e, strict=False) if en > 0.02]
    ch = Chequeo(
        cabeza_dif_max=round(cab, 4),
        ojos_violeta=round(ojos, 2),
        boca_voz=round(_pearson(boca, e), 3),
        boca_mueve=round(sum(voz) / max(1, len(voz)), 4),
        pasa=True,
    )
    if ch.cabeza_dif_max > UMBRALES["cabeza_dif_max"]:
        ch.motivos.append("la cabeza cambia")
    if not UMBRALES["ojos_min"] <= ch.ojos_violeta <= UMBRALES["ojos_max"]:
        ch.motivos.append("los ojos cambian")
    if ch.boca_voz < UMBRALES["boca_voz_min"]:
        ch.motivos.append("la boca no sigue la voz")
    if ch.boca_mueve < UMBRALES["boca_mueve_min"]:
        ch.motivos.append("la boca casi no se mueve")
    ch.pasa = not ch.motivos
    return ch


# ── 5. armar ──────────────────────────────────────────────────────────────────────────────────


def armar(
    clips: list[Path], audio: Path, destino: Path, ancho: int, alto: int, cortes: bool
) -> Path:
    """Une los tramos y les pone el audio original. Con `cortes`, los tramos impares van en
    primer plano (zoom 1,25 sobre la cabeza): un corte de cámara barato, sin otra llamada."""
    partes = []
    for i, c in enumerate(clips):
        p = destino.with_name(f"_parte_{i}.mp4")
        filtro = f"scale={ancho}:{alto}"
        if cortes and i % 2 == 1:
            filtro = f"crop=iw/1.25:ih/1.25:(iw-iw/1.25)/2:0,scale={ancho}:{alto}"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(c),
                "-an",
                "-vf",
                filtro,
                "-r",
                str(FPS),
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                str(p),
            ],
            check=True,
        )
        partes.append(p)
    lista = destino.with_name("_lista.txt")
    lista.write_text("".join(f"file '{p.name}'\n" for p in partes))
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lista),
            "-i",
            str(audio),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(destino),
        ],
        check=True,
    )
    for p in [*partes, lista]:
        p.unlink(missing_ok=True)
    return destino


# ── 6. registro ───────────────────────────────────────────────────────────────────────────────


def guardar(corrida: dict, carpeta: Path) -> None:
    (carpeta / "corrida.json").write_text(
        json.dumps(corrida, indent=1, ensure_ascii=False, default=_json)
    )


def _json(o):
    if hasattr(o, "__dataclass_fields__"):
        return asdict(o)
    return str(o)


# ── 5b. dirección de cámara (Spec-810: lo que hace Omni, en Python) ──────────────────────────

PLANOS = {  # zoom sobre la cabeza y corrimiento horizontal (fracción del ancho)
    "medio": (1.0, 0.0),
    "cerrado": (1.35, 0.0),
    "lateral": (1.18, 0.12),
    "ojos": (1.9, 0.0),
}


def _ruido(t: float, semilla: float) -> float:
    """Ruido suave en -1..1 (suma de senos): cámara en mano y la llama que titila."""
    return (
        math.sin(t * 1.3 + semilla) * 0.5
        + math.sin(t * 2.9 + semilla * 1.7) * 0.3
        + math.sin(t * 6.1 + semilla * 2.3) * 0.2
    )


def _picos(e: list[float]) -> list[int]:
    """Las palabras fuertes: máximos locales de energía por encima del 75 % del máximo."""
    tope = max(e) if e else 0
    return [i for i in range(2, len(e) - 2) if e[i] > 0.75 * tope and e[i] == max(e[i - 2 : i + 3])]


def _niebla(ancho: int, alto: int, semilla: int = 7) -> Image.Image:
    import random

    rnd = random.Random(semilla)
    chica = Image.new("L", (ancho // 16 + 2, alto // 16 + 2))
    chica.putdata([rnd.randint(0, 255) for _ in range(chica.width * chica.height)])
    return chica.resize((ancho * 2, alto), Image.Resampling.BICUBIC).filter(
        ImageFilter.GaussianBlur(18)
    )


def dirigir(
    clips: list[Path],
    audio: Path,
    destino: Path,
    ancho: int,
    alto: int,
    planos: list[str],
    niebla: float = 0.10,
    mano_px: float = 3.0,
    llama: float = 0.04,
    ojos_latido: float = 0.8,
) -> Path:
    """Arma el video con dirección de cámara: un plano por tramo (corte en cada unión), un
    acercamiento lento dentro del tramo, un golpe de zoom en las palabras fuertes, cámara en mano,
    la luz que titila, los ojos que laten con la voz y niebla que se mueve. Audio original."""
    from PIL import ImageEnhance

    tmp = destino.with_name("_dirigir")
    tmp.mkdir(exist_ok=True)
    cuadros: list[tuple[Path, int, int]] = []  # (archivo, tramo, índice en el tramo)
    for i, c in enumerate(clips):
        cs = cuadros_de(c, tmp / f"t{i}")
        cuadros += [(f, i, k) for k, f in enumerate(cs)]
    e = energia(muestras(audio), 1 / FPS)
    e += [0.0] * max(0, len(cuadros) - len(e))
    tope = max(e) or 1
    picos = _picos(e)
    golpe = [0.0] * len(cuadros)
    for p in picos:
        for d in range(8):
            if p + d < len(golpe):
                golpe[p + d] = max(golpe[p + d], 0.08 * (1 - d / 8))
    largo_tramo = {i: sum(1 for _, t, _ in cuadros if t == i) for i in range(len(clips))}
    centro, cab_top = {}, {}
    for i in range(len(clips)):
        primero = Image.open(next(f for f, t, _ in cuadros if t == i)).convert("RGB")
        z = zonas(primero)
        cab, ojos = z.cabeza, z.ojos
        cab_top[i] = cab[1] - 0.25 * (
            cab[3] - cab[1]
        )  # el tallo y los auriculares, arriba de lo naranja
        centro[i] = (
            (cab[0] + cab[2]) / 2,
            (cab[1] + cab[3]) / 2,
            (ojos[0] + ojos[2]) / 2,
            (ojos[1] + ojos[3]) / 2,
        )
    bruma = _niebla(ancho, alto)
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{ancho}x{alto}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-i",
            str(audio),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-crf",
            "21",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(destino),
        ],
        stdin=subprocess.PIPE,
    )
    for n, (f, i, k) in enumerate(cuadros):
        im = Image.open(f).convert("RGB").resize((ancho, alto), Image.Resampling.LANCZOS)
        t = n / FPS
        # los ojos laten con la voz (antes de mover la cámara, sobre los ojos detectados)
        if ojos_latido:
            caja = tuple(int(v) for v in zonas(im).ojos)
            m = Image.new("L", im.size, 0)
            m.paste(violeta(im).crop(caja), caja[:2])
            m = m.filter(ImageFilter.GaussianBlur(2))
            brillo = ImageEnhance.Brightness(im).enhance(1 + ojos_latido * e[n] / tope)
            im = Image.composite(brillo, im, m)
        zoom0, corrido = PLANOS[planos[i % len(planos)]]
        zoom = zoom0 * (1 + 0.06 * k / max(1, largo_tramo[i])) * (1 + golpe[n])
        cx, cy, ox, oy = centro[i]
        if planos[i % len(planos)] == "ojos":
            cx, cy = ox, oy
        cx += corrido * ancho + mano_px * _ruido(t, 1.0) * zoom
        cy += mano_px * _ruido(t, 4.0) * zoom
        w, h = ancho / zoom, alto / zoom
        x0 = min(max(0, cx - w / 2), ancho - w)
        y0 = cy - h / 2.6  # la cabeza en el tercio de arriba…
        y0 = min(y0, cab_top[i] - 0.06 * h)  # …pero entera: el tallo no se corta
        y0 = min(max(0, y0), alto - h)
        im = im.crop((round(x0), round(y0), round(x0 + w), round(y0 + h))).resize(
            (ancho, alto), Image.Resampling.BICUBIC
        )
        im = ImageEnhance.Brightness(im).enhance(1 + llama * _ruido(t * 3, 9.0))
        if niebla:
            dx = int((t * 18) % ancho)
            capa = bruma.crop((dx, 0, dx + ancho, alto)).convert("RGB")
            im = Image.blend(im, ImageChops.screen(im, capa), niebla)
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    proc.wait()
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)
    return destino


# ── 5c. multicámara: cortar entre dos tomas sincronizadas (Spec-810 V3b) ──────────────────────


def _cubrir(im: Image.Image, ancho: int, alto: int, arriba: float = 0.42) -> Image.Image:
    """Escala para cubrir el cuadro y recorta (la cabeza queda arriba del centro)."""
    s = max(ancho / im.width, alto / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.Resampling.LANCZOS)
    x0 = (im.width - ancho) // 2
    y0 = round((im.height - alto) * arriba)
    return im.crop((x0, y0, x0 + ancho, y0 + alto))


def plan_cortes(e: list[float], n: int, cada: tuple[float, float] = (1.5, 2.5)) -> list[int]:
    """Los cuadros donde se corta: cada 1,5–2,5 s, en el momento de menos voz de esa ventana."""
    cortes, i = [], 0
    while True:
        a, b = i + round(cada[0] * FPS), i + round(cada[1] * FPS)
        if b >= n - round(0.6 * FPS):
            break
        ventana = range(a, min(b, n))
        j = min(ventana, key=lambda k: e[k] if k < len(e) else 0)
        cortes.append(j)
        i = j
    return cortes


def multicamara(
    pares: list[tuple[Path, Path]],
    audio: Path,
    destino: Path,
    ancho: int,
    alto: int,
    mano_px: float = 2.5,
    llama: float = 0.03,
) -> Path:
    """Dos tomas por tramo (plano medio, primer plano) con el mismo audio: se corta entre ellas
    cada 1,5–2,5 s en los silencios cortos, y en cada unión de tramos. Encima, la cámara en mano,
    un acercamiento lento por toma, un golpe de zoom en las palabras fuertes y la luz que titila.
    El audio, siempre el original."""
    import shutil

    from PIL import ImageEnhance

    tmp = destino.with_name("_multicam")
    tmp.mkdir(exist_ok=True)
    e = energia(muestras(audio), 1 / FPS)
    picos = set(_picos(e))
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{ancho}x{alto}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-i",
            str(audio),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(destino),
        ],
        stdin=subprocess.PIPE,
    )
    n_total, toma = 0, 0
    for i, (medio, cerca) in enumerate(pares):
        tm = cuadros_de(medio, tmp / f"m{i}")
        tc = cuadros_de(cerca, tmp / f"c{i}")
        n = min(len(tm), len(tc))
        cortes = set(plan_cortes(e[n_total : n_total + n], n))
        desde = 0
        golpe = 0.0
        for k in range(n):
            if k in cortes:
                toma, desde = 1 - toma, k
            t = (n_total + k) / FPS
            src = tc[k] if toma else tm[k]
            im = _cubrir(
                Image.open(src).convert("RGB"), ancho, alto, 0.62 if toma else 0.0
            )  # primer plano: ojos y boca
            if n_total + k in picos:
                golpe = 0.07
            golpe *= 0.85
            zoom = (1 + 0.05 * (k - desde) / max(1, n)) * (1 + golpe)
            cx = ancho / 2 + mano_px * _ruido(t, 1.0)
            cy = alto / 2 + mano_px * _ruido(t, 4.0)
            w, h = ancho / zoom, alto / zoom
            x0 = min(max(0, cx - w / 2), ancho - w)
            y0 = min(max(0, cy - h / 2), alto - h)
            im = im.crop((round(x0), round(y0), round(x0 + w), round(y0 + h))).resize(
                (ancho, alto), Image.Resampling.BICUBIC
            )
            im = ImageEnhance.Brightness(im).enhance(1 + llama * _ruido(t * 3, 9.0))
            proc.stdin.write(im.tobytes())
        n_total += n
        toma = 1 - toma  # en la unión de tramos también se cambia de cámara
    proc.stdin.close()
    proc.wait()
    shutil.rmtree(tmp, ignore_errors=True)
    return destino
