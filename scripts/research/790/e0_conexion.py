"""Spike E0 (Spec-790 §10.0): ¿el sitio maneja ComfyUI de punta a punta?

Corre igual en el host y dentro de `narrative-api-dev` (copiado a /tmp):
    uv run python e0_conexion.py --donde host
    docker cp … ; docker exec narrative-api-dev /app/.venv/bin/python /tmp/e790/e0_conexion.py \
        --donde contenedor --url http://host.docker.internal:8188

Imprime un JSON con cada prueba: ida y vuelta (WebSocket y polling, 5 veces cada una),
error de validación, error al ejecutar, ComfyUI apagado, WebSocket cortado a mitad de
camino, dos pedidos a la vez con y sin lock, /free y los nodos que hacen falta.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import Comfy, ComfyError, grafo_trivial  # noqa: E402

NODOS = [
    "LoadImage",
    "SaveImage",
    "EmptyQwenImageLayeredLatentImage",
    "EmptyFlux2LatentImage",
    "TextEncodeQwenImageEditPlus",
    "LoadBackgroundRemovalModel",
    "RemoveBackground",
    "ZImageFunControlnet",
    "InpaintModelConditioning",
    "ControlNetApplyAdvanced",
    "LoraLoaderModelOnly",
    "ModelSamplingAuraFlow",
    "IPAdapterAdvanced",
    "ImageStitch",
]


def png_de_prueba() -> Path:
    from PIL import Image

    ruta = Path("/tmp/e790_prueba.png")
    Image.new("RGB", (1280, 720), (30, 30, 40)).save(ruta)
    return ruta


class ComfyConCorte(Comfy):
    """Simula que el WebSocket se corta después del primer mensaje."""

    async def _esperar_ws(self, ws, prompt_id, eventos, inicio):
        await ws.recv()
        raise ConnectionResetError("corte simulado")


async def ida_y_vuelta(url: str, usar_ws: bool, veces: int = 5) -> dict:
    tiempos, vias = [], []
    async with Comfy(url) as c:
        nombre = await c.subir(png_de_prueba())
        for i in range(veces):
            # Un prefijo distinto cada vez evita que ComfyUI devuelva todo desde su caché.
            r = await c.correr(
                grafo_trivial(nombre, f"spec790/e0_{int(time.time() * 1000)}_{i}"),
                usar_ws=usar_ws,
                medir_vram=False,
            )
            tiempos.append(r.segundos)
            vias.append(r.via)
    return {"segundos": tiempos, "mediana": statistics.median(tiempos), "vias": sorted(set(vias))}


async def subir_y_bajar(url: str) -> dict:
    """Tiempo de subir un PNG de 1280 × 720 y de bajar el resultado (lo que suma cada paso)."""
    async with Comfy(url) as c:
        src = png_de_prueba()
        t = time.monotonic()
        nombre = await c.subir(src)
        t_subir = time.monotonic() - t
        r = await c.correr(
            grafo_trivial(nombre, f"spec790/e0_bajar_{int(time.time())}"), medir_vram=False
        )
        t = time.monotonic()
        await c.bajar(r.imagenes[0], Path("/tmp/e790_bajada.png"))
        return {"subir_s": round(t_subir, 3), "bajar_s": round(time.monotonic() - t, 3)}


async def error_de_validacion(url: str) -> dict:
    async with Comfy(url) as c:
        try:
            await c.correr(grafo_trivial("no_existe_esta_imagen.png"), medir_vram=False)
        except ComfyError as e:
            return {"mensaje": str(e), "detalle": e.detalle[:300]}
    return {"mensaje": "NO FALLÓ"}


async def error_al_ejecutar(url: str) -> dict:
    """Un grafo que pasa la validación y falla al correr: pedir el canal alfa de una imagen
    RGB (ImageToMask con `alpha` sobre 3 canales → IndexError dentro de ComfyUI)."""
    async with Comfy(url) as c:
        nombre = await c.subir(png_de_prueba())
        grafo = {
            "1": {"class_type": "LoadImage", "inputs": {"image": nombre}},
            "2": {"class_type": "ImageToMask", "inputs": {"image": ["1", 0], "channel": "alpha"}},
            "3": {"class_type": "MaskToImage", "inputs": {"mask": ["2", 0]}},
            "4": {
                "class_type": "SaveImage",
                "inputs": {"images": ["3", 0], "filename_prefix": f"spec790/e0_err_{time.time()}"},
            },
        }
        try:
            r = await c.correr(grafo, medir_vram=False)
            return {"mensaje": "NO FALLÓ (ComfyUI ajustó los tamaños solo)", "via": r.via}
        except ComfyError as e:
            return {"mensaje": str(e), "detalle": e.detalle[:300]}


async def apagado() -> dict:
    async with Comfy("http://127.0.0.1:8199") as c:
        try:
            await c.stats()
        except ComfyError as e:
            return {"mensaje": str(e)}
    return {"mensaje": "NO FALLÓ"}


async def websocket_cortado(url: str) -> dict:
    async with ComfyConCorte(url) as c:
        nombre = await c.subir(png_de_prueba())
        r = await c.correr(
            grafo_trivial(nombre, f"spec790/e0_corte_{int(time.time())}"), medir_vram=False
        )
        return {"via": r.via, "eventos": r.eventos, "imagenes": len(r.imagenes)}


async def websocket_sin_conexion(url: str) -> dict:
    async with Comfy(url) as c:
        c.ws_url = "ws://127.0.0.1:8199"  # el WebSocket no conecta; el HTTP sí
        nombre = await c.subir(png_de_prueba())
        r = await c.correr(
            grafo_trivial(nombre, f"spec790/e0_sinws_{int(time.time())}"), medir_vram=False
        )
        return {"via": r.via, "eventos": r.eventos, "imagenes": len(r.imagenes)}


async def dos_a_la_vez(url: str, con_lock: bool) -> dict:
    """Dos pedidos lanzados juntos. Con lock, el segundo no se encola hasta que termina el
    primero (lo que el sitio necesita para mirar la VRAM entre pasos)."""
    lock = asyncio.Lock()
    marcas: list[tuple[str, str, float]] = []
    t0 = time.monotonic()

    async def uno(nombre_tarea: str):
        async def correr():
            async with Comfy(url) as c:
                nombre = await c.subir(png_de_prueba())
                marcas.append((nombre_tarea, "empieza", round(time.monotonic() - t0, 2)))
                await c.correr(
                    grafo_trivial(nombre, f"spec790/e0_{nombre_tarea}_{time.time()}"),
                    medir_vram=False,
                )
                marcas.append((nombre_tarea, "termina", round(time.monotonic() - t0, 2)))

        if con_lock:
            async with lock:
                await correr()
        else:
            await correr()

    await asyncio.gather(uno("A"), uno("B"))
    orden = [f"{n} {q} {t}s" for n, q, t in sorted(marcas, key=lambda m: m[2])]
    en_serie = orden[0].split()[0] == orden[1].split()[0]
    return {"orden": orden, "en_serie": en_serie}


async def liberar(url: str) -> dict:
    async with Comfy(url) as c:
        antes = await c.vram_libre_mb()
        await c.liberar()
        await asyncio.sleep(1)
        return {
            "vram_libre_antes_mb": round(antes),
            "vram_libre_despues_mb": round(await c.vram_libre_mb()),
        }


async def nodos(url: str) -> dict:
    async with Comfy(url) as c:
        r = await c.http.get("/object_info")
        info = r.json()
        st = await c.stats()
    return {
        "comfyui": st["system"].get("comfyui_version"),
        "python": st["system"].get("python_version", "")[:6],
        "gpu": st["devices"][0].get("name"),
        "vram_total_mb": round(st["devices"][0]["vram_total"] / 2**20),
        "faltan": [n for n in NODOS if n not in info],
        "estan": [n for n in NODOS if n in info],
    }


async def main(url: str, donde: str) -> dict:
    res = {"donde": donde, "url": url}
    for nombre, coro in [
        ("nodos", nodos(url)),
        ("ida_y_vuelta_websocket", ida_y_vuelta(url, True)),
        ("ida_y_vuelta_polling", ida_y_vuelta(url, False)),
        ("subir_y_bajar", subir_y_bajar(url)),
        ("error_de_validacion", error_de_validacion(url)),
        ("error_al_ejecutar", error_al_ejecutar(url)),
        ("apagado", apagado()),
        ("websocket_cortado", websocket_cortado(url)),
        ("websocket_sin_conexion", websocket_sin_conexion(url)),
        ("dos_a_la_vez_sin_lock", dos_a_la_vez(url, False)),
        ("dos_a_la_vez_con_lock", dos_a_la_vez(url, True)),
        ("liberar", liberar(url)),
    ]:
        try:
            res[nombre] = await coro
        except Exception as e:  # la prueba misma falló: se reporta, no se esconde
            res[nombre] = {"FALLO_DE_LA_PRUEBA": f"{type(e).__name__}: {e}"}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8188")
    ap.add_argument("--donde", default="host")
    a = ap.parse_args()
    print(json.dumps(asyncio.run(main(a.url, a.donde)), ensure_ascii=False, indent=2))
