"""Herramientas comunes de los spikes de la Spec-790 (T0.2). Descartable: no importa `src/`.

- `Comfy`: cliente asíncrono mínimo de ComfyUI (httpx + websockets), el camino que el sitio
  va a usar en producción (T2 de la spec). Sube imágenes, encola, sigue el avance por
  WebSocket (o por *polling* de /history si el WebSocket se corta), baja, libera memoria.
- `MedidorVram`: muestrea la VRAM usada de toda la placa mientras corre un paso.
- `grilla()`: hoja de contacto (variante × semilla) con una fila a 120 px.
- `informe()`: escribe el informe del spike en Markdown.

Corre con el venv del proyecto (`uv run python …`) o dentro de `narrative-api-dev`
(`/app/.venv/bin/python`), que tiene httpx y websockets.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx

AQUI = Path(__file__).resolve().parent
INSUMOS = AQUI / "insumos"
COMFY_URL = os.environ.get("COMFY_URL", "http://localhost:8188")


class ComfyError(RuntimeError):
    """Un error de ComfyUI contado en castellano, con el detalle técnico aparte."""

    def __init__(self, mensaje: str, detalle: str = ""):
        super().__init__(mensaje)
        self.detalle = detalle


@dataclass
class Resultado:
    prompt_id: str
    segundos: float
    imagenes: list[dict]                      # [{"filename", "subfolder", "type"}]
    eventos: list[str] = field(default_factory=list)
    via: str = "websocket"                    # o "polling" si se cortó el WebSocket
    vram_pico_mb: float | None = None


class Comfy:
    """Cliente mínimo. Un objeto por spike; `async with Comfy() as c:`."""

    def __init__(self, url: str = COMFY_URL, timeout: float = 900):
        self.url = url.rstrip("/")
        self.ws_url = self.url.replace("http://", "ws://").replace("https://", "wss://")
        self.client_id = str(uuid.uuid4())
        self.timeout = timeout
        self.http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "Comfy":
        self.http = httpx.AsyncClient(base_url=self.url, timeout=60)
        return self

    async def __aexit__(self, *exc) -> None:
        if self.http:
            await self.http.aclose()

    # ── lo básico ────────────────────────────────────────────────────────────
    async def stats(self) -> dict:
        try:
            r = await self.http.get("/system_stats", timeout=5)
        except httpx.ConnectError as e:
            raise ComfyError("La compu que hace las imágenes está apagada", repr(e)) from None
        r.raise_for_status()
        return r.json()

    async def vram_libre_mb(self) -> float:
        d = (await self.stats())["devices"][0]
        return d["vram_free"] / 2**20

    async def subir(self, ruta: Path, subcarpeta: str = "spec790") -> str:
        with open(ruta, "rb") as f:
            r = await self.http.post(
                "/upload/image",
                files={"image": (ruta.name, f, "image/png")},
                data={"overwrite": "true", "subfolder": subcarpeta, "type": "input"},
            )
        r.raise_for_status()
        info = r.json()
        return f"{info['subfolder']}/{info['name']}" if info.get("subfolder") else info["name"]

    async def encolar(self, grafo: dict) -> str:
        r = await self.http.post("/prompt", json={"prompt": grafo, "client_id": self.client_id})
        if r.status_code != 200:
            raise ComfyError("ComfyUI no aceptó el pedido", r.text[:3000])
        return r.json()["prompt_id"]

    async def historia(self, prompt_id: str) -> dict | None:
        r = await self.http.get(f"/history/{prompt_id}")
        r.raise_for_status()
        return r.json().get(prompt_id)

    async def bajar(self, imagen: dict, destino: Path) -> Path:
        r = await self.http.get("/view", params=imagen, timeout=120)
        r.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        return destino

    async def liberar(self) -> None:
        await self.http.post("/free", json={"unload_models": True, "free_memory": True})

    async def interrumpir(self) -> None:
        await self.http.post("/interrupt")

    # ── correr un grafo y esperar ────────────────────────────────────────────
    async def correr(self, grafo: dict, *, usar_ws: bool = True, medir_vram: bool = True) -> Resultado:
        """Encola y espera. Sigue el avance por WebSocket; si se corta, cae a /history."""
        medidor = MedidorVram(self) if medir_vram else None
        inicio = time.monotonic()
        eventos: list[str] = []
        via = "websocket" if usar_ws else "polling"
        prompt_id: str | None = None
        async with _quizas(medidor):
            if usar_ws:
                try:
                    import websockets

                    # Conectar ANTES de encolar, para no perder los primeros eventos.
                    async with websockets.connect(
                        f"{self.ws_url}/ws?clientId={self.client_id}", max_size=None, open_timeout=10
                    ) as ws:
                        prompt_id = await self.encolar(grafo)
                        await self._esperar_ws(ws, prompt_id, eventos, inicio)
                except ComfyError:
                    raise
                except Exception as e:  # sin conexión, conexión cortada, sin la librería…
                    eventos.append(f"websocket cortado: {type(e).__name__} → polling")
                    via = "polling"
            if via == "polling":
                prompt_id = prompt_id or await self.encolar(grafo)
                await self._esperar_polling(prompt_id, inicio)
        entrada = await self.historia(prompt_id)
        if entrada is None:
            raise ComfyError("ComfyUI terminó pero no dejó el resultado", prompt_id)
        estado = entrada.get("status", {})
        if estado.get("status_str") == "error":
            raise ComfyError("ComfyUI falló al hacer la imagen", json.dumps(estado)[:3000])
        imagenes = [img for salida in entrada.get("outputs", {}).values() for img in salida.get("images", [])]
        return Resultado(
            prompt_id=prompt_id,
            segundos=round(time.monotonic() - inicio, 2),
            imagenes=imagenes,
            eventos=eventos,
            via=via,
            vram_pico_mb=medidor.pico_mb if medidor else None,
        )

    async def _esperar_ws(self, ws, prompt_id: str, eventos: list[str], inicio: float) -> None:
        while True:
            restante = self.timeout - (time.monotonic() - inicio)
            if restante <= 0:
                raise ComfyError("ComfyUI tardó demasiado", f"timeout {self.timeout}s")
            msg = await asyncio.wait_for(ws.recv(), timeout=restante)
            if isinstance(msg, bytes):  # vistas previas: no interesan
                continue
            m = json.loads(msg)
            tipo, data = m.get("type"), m.get("data", {})
            if data.get("prompt_id") not in (None, prompt_id):
                continue
            if tipo in ("execution_start", "execution_cached", "execution_success"):
                eventos.append(tipo)
            elif tipo == "progress":
                eventos.append(f"progress {data.get('value')}/{data.get('max')}")
            elif tipo == "execution_error":
                raise ComfyError(
                    "ComfyUI falló al hacer la imagen",
                    f"{data.get('node_type')}: {data.get('exception_message', '')}"[:3000],
                )
            elif tipo == "executing" and data.get("node") is None and data.get("prompt_id") == prompt_id:
                eventos.append("fin")
                return

    async def _esperar_polling(self, prompt_id: str, inicio: float, cada: float = 1.0) -> None:
        while time.monotonic() - inicio < self.timeout:
            entrada = await self.historia(prompt_id)
            if entrada is not None and entrada.get("status", {}).get("completed", True):
                return
            if entrada is not None and entrada.get("status", {}).get("status_str") == "error":
                return
            await asyncio.sleep(cada)
        raise ComfyError("ComfyUI tardó demasiado", f"timeout {self.timeout}s")


class MedidorVram:
    """Muestrea la VRAM usada (toda la placa, vía /system_stats) mientras corre un paso."""

    def __init__(self, comfy: Comfy, cada: float = 0.5):
        self.comfy, self.cada = comfy, cada
        self.pico_mb: float | None = None
        self._tarea: asyncio.Task | None = None

    async def _muestrear(self) -> None:
        while True:
            try:
                d = (await self.comfy.stats())["devices"][0]
                usado = (d["vram_total"] - d["vram_free"]) / 2**20
                self.pico_mb = max(self.pico_mb or 0, round(usado))
            except Exception:
                pass
            await asyncio.sleep(self.cada)

    async def __aenter__(self):
        self._tarea = asyncio.create_task(self._muestrear())
        return self

    async def __aexit__(self, *exc):
        if self._tarea:
            self._tarea.cancel()


@asynccontextmanager
async def _quizas(cm):
    if cm is None:
        yield None
    else:
        async with cm as v:
            yield v


def grafo_trivial(imagen_subida: str, prefijo: str = "spec790/e0") -> dict:
    """Cargar una imagen y guardarla: lo mínimo para probar la ida y vuelta."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": imagen_subida}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": prefijo}},
    }


# ── grilla y informe ─────────────────────────────────────────────────────────
def grilla(filas: list[tuple[str, list[tuple[str, Path]]]], destino: Path, ancho_celda: int = 384) -> Path:
    """Hoja de contacto: una fila por variante, una celda por semilla, y debajo de cada
    fila la misma fila a 120 px de ancho (el tamaño de la miniatura en el celular)."""
    from PIL import Image, ImageDraw, ImageFont

    fuente = ImageFont.load_default(size=16)
    alto_celda = int(ancho_celda * 9 / 16)
    cols = max(len(c) for _, c in filas)
    margen, rotulo = 8, 170
    alto_fila = alto_celda + 24 + 68 + margen
    hoja = Image.new("RGB", (rotulo + cols * (ancho_celda + margen), len(filas) * alto_fila + margen), (24, 24, 24))
    d = ImageDraw.Draw(hoja)
    for i, (nombre, celdas) in enumerate(filas):
        y = margen + i * alto_fila
        d.text((8, y + alto_celda // 2), nombre, font=fuente, fill=(230, 230, 230))
        for j, (leyenda, ruta) in enumerate(celdas):
            x = rotulo + j * (ancho_celda + margen)
            im = Image.open(ruta).convert("RGB")
            im.thumbnail((ancho_celda, alto_celda))
            hoja.paste(im, (x, y))
            d.text((x, y + alto_celda + 2), leyenda, font=fuente, fill=(180, 180, 180))
            chico = Image.open(ruta).convert("RGB")
            chico.thumbnail((120, 68))
            hoja.paste(chico, (x, y + alto_celda + 22))
    destino.parent.mkdir(parents=True, exist_ok=True)
    hoja.save(destino)
    return destino


def informe(destino: Path, titulo: str, secciones: dict[str, str]) -> Path:
    """Informe del spike: título, fecha y secciones en orden (Pregunta, Variantes, Medidas,
    Lo que se ve, Propuesta). Las imágenes quedan en salidas/ (fuera de git)."""
    texto = [f"# {titulo}", "", f"_{time.strftime('%Y-%m-%d %H:%M')}_", ""]
    for nombre, cuerpo in secciones.items():
        texto += [f"## {nombre}", "", cuerpo.strip(), ""]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(texto), encoding="utf-8")
    return destino
