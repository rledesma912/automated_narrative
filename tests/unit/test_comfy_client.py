"""Spec-790: el cliente de ComfyUI llena el workflow y, al cancelar, corta lo que pidió."""

import asyncio
import json

import httpx
import pytest
from PIL import Image

from src.infrastructure.adapters.comfy.client import ComfyClient, ComfyError


def _cliente(handler) -> ComfyClient:
    c = ComfyClient(url="http://comfy.test")
    c._http = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=c.url)
    return c


async def test_cancelar_saca_el_pedido_y_lo_interrumpe(tmp_path):
    pedidos: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        pedidos.append((req.method, req.url.path))
        if req.url.path == "/upload/image":
            return httpx.Response(200, json={"name": "boceto.png", "subfolder": "spec790"})
        if req.url.path == "/prompt":
            grafo = json.loads(req.content)["prompt"]
            assert grafo["9"]["inputs"]["prompt"] == "hola"  # params.yaml: prompt → nodo 9
            return httpx.Response(200, json={"prompt_id": "p1"})
        if req.url.path.startswith("/history"):
            return httpx.Response(200, json={})  # todavía corriendo
        if req.url.path == "/queue" and req.method == "GET":
            return httpx.Response(200, json={"queue_running": [[1, "p1", {}]], "queue_pending": []})
        return httpx.Response(200, json={})

    boceto = tmp_path / "b.png"
    Image.new("RGB", (8, 8)).save(boceto)
    tarea = asyncio.create_task(
        _cliente(handler).correr(
            "boceto_a_imagen",
            {"prompt": "hola", "semilla": 1},
            {"boceto": boceto},
            tmp_path / "o.png",
        )
    )
    await asyncio.sleep(0.2)
    tarea.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarea
    assert ("POST", "/queue") in pedidos
    assert ("POST", "/interrupt") in pedidos


async def test_comfy_apagado_da_un_mensaje_para_la_pantalla():
    def handler(_req):
        raise httpx.ConnectError("apagado")

    with pytest.raises(ComfyError) as e:
        await _cliente(handler).vram_libre_mb()
    assert "apagada" in str(e.value)
