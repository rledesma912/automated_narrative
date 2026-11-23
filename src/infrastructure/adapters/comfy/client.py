"""Cliente de ComfyUI (Spec-790 T2, E0): subir, encolar, esperar, bajar, liberar.

Una llamada = una sola tarea (D15). Espera por *polling* de `/history` (E0: anda igual que el
WebSocket y es más simple). Los errores llegan como `ComfyError` con el mensaje para la pantalla
y el detalle técnico aparte.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Protocol

import httpx

from src.config import settings
from src.messages import message

WORKFLOWS = Path("config/miniatura/workflows")


class ComfyError(RuntimeError):
    def __init__(self, mensaje: str, detalle: str = ""):
        super().__init__(mensaje)
        self.detalle = detalle


class ComfyPort(Protocol):
    """Lo que el arnés necesita de ComfyUI (el real o el de los tests)."""

    async def vram_libre_mb(self) -> float: ...
    async def correr(
        self, receta: str, valores: dict, entradas: dict[str, Path], destino: Path
    ) -> Path: ...
    async def liberar(self) -> None: ...


def cargar_workflow(receta: str) -> tuple[dict, dict]:
    import yaml

    base = WORKFLOWS / receta
    grafo = json.loads((base / "workflow.api.json").read_text(encoding="utf-8"))
    params = yaml.safe_load((base / "params.yaml").read_text(encoding="utf-8"))["params"]
    for nombre, p in params.items():
        if str(p["node"]) not in grafo:
            raise ComfyError(
                message(
                    "miniatura.error_comfy",
                    detalle=message(
                        "miniatura.falta_nodo", receta=receta, nodo=p["node"], nombre=nombre
                    ),
                )
            )
    return grafo, params


def llenar(grafo: dict, params: dict, valores: dict) -> dict:
    g = json.loads(json.dumps(grafo))
    for nombre, valor in valores.items():
        p = params[nombre]
        g[str(p["node"])]["inputs"][p["input"]] = valor
    return g


class ComfyClient:
    def __init__(self, url: str | None = None, timeout: float = 900):
        self.url = (url or settings.comfy_url).rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid.uuid4())

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.url, timeout=60)

    async def _get(self, ruta: str, **kw) -> httpx.Response:
        try:
            async with self._http() as h:
                r = await h.get(ruta, **kw)
        except httpx.HTTPError as e:
            raise ComfyError(message("miniatura.sin_comfy"), repr(e)) from None
        r.raise_for_status()
        return r

    async def vram_libre_mb(self) -> float:
        d = (await self._get("/system_stats", timeout=5)).json()["devices"][0]
        return d["vram_free"] / 2**20

    async def subir(self, ruta: Path) -> str:
        try:
            async with self._http() as h:
                with ruta.open("rb") as f:
                    r = await h.post(
                        "/upload/image",
                        files={"image": (f"{uuid.uuid4().hex[:8]}_{ruta.name}", f, "image/png")},
                        data={"subfolder": "spec790", "overwrite": "true"},
                    )
        except httpx.HTTPError as e:
            raise ComfyError(message("miniatura.sin_comfy"), repr(e)) from None
        r.raise_for_status()
        d = r.json()
        return f"{d['subfolder']}/{d['name']}" if d.get("subfolder") else d["name"]

    async def liberar(self) -> None:
        try:
            async with self._http() as h:
                await h.post("/free", json={"unload_models": True, "free_memory": True})
        except httpx.HTTPError:
            pass

    async def correr(
        self, receta: str, valores: dict, entradas: dict[str, Path], destino: Path
    ) -> Path:
        """Corre una receta: sube las entradas (imágenes), llena el grafo, espera y baja la
        primera imagen de salida en `destino`."""
        grafo, params = cargar_workflow(receta)
        for nombre, ruta in entradas.items():
            valores[nombre] = await self.subir(ruta)
        valores.setdefault("prefijo", f"spec790/{receta}")
        g = llenar(grafo, params, valores)
        try:
            async with self._http() as h:
                r = await h.post("/prompt", json={"prompt": g, "client_id": self.client_id})
        except httpx.HTTPError as e:
            raise ComfyError(message("miniatura.sin_comfy"), repr(e)) from None
        if r.status_code != 200:
            raise ComfyError(message("miniatura.error_comfy", detalle=receta), r.text[:800])
        prompt_id = r.json()["prompt_id"]
        inicio = time.monotonic()
        while True:
            hist = (await self._get(f"/history/{prompt_id}")).json().get(prompt_id)
            if hist:
                st = hist.get("status", {})
                if st.get("status_str") == "error":
                    raise ComfyError(
                        message("miniatura.error_comfy", detalle=receta), json.dumps(st)[:800]
                    )
                if st.get("completed") or hist.get("outputs"):
                    break
            if time.monotonic() - inicio > self.timeout:
                raise ComfyError(
                    message(
                        "miniatura.error_comfy",
                        detalle=message("miniatura.tardo_demasiado", receta=receta),
                    )
                )
            await asyncio.sleep(1.0)
        imagenes = [im for out in hist.get("outputs", {}).values() for im in out.get("images", [])]
        if not imagenes:
            raise ComfyError(message("miniatura.error_comfy", detalle=f"{receta}: sin imagen"))
        im = imagenes[0]
        r = await self._get(
            "/view",
            params={
                "filename": im["filename"],
                "subfolder": im.get("subfolder", ""),
                "type": im.get("type", "output"),
            },
        )
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        return destino
