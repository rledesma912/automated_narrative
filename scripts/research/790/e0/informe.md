# Spike E0 — Conexión con ComfyUI (Spec-790 §10.0)

_2026-11-22. Scripts: `e0_conexion.py` y `e0_vram.py`. Datos crudos en `e0/salidas/` (fuera de git)._

## Pregunta

¿El sitio, desde su contenedor, maneja ComfyUI de punta a punta?

## Entorno

| | |
|---|---|
| ComfyUI | 0.28.3, Python 3.12, en el host (`:8188`) |
| GPU | RTX 3060, 11 909 MB que ve ComfyUI; ~1,1 GB ocupados por otros procesos (audiogen vLLM en reposo, el navegador, sunshine) |
| Cliente | `comun.Comfy`: `httpx.AsyncClient` + `websockets` 16.0. Las dos ya están en el venv del contenedor de dev (`websockets` llega con `uvicorn[standard]`): **no suma dependencias** |

## Resultados (iguales en el host y en `narrative-api-dev` vía `host.docker.internal:8188`)

| Prueba | Resultado |
|---|---|
| Nodos que hacen falta | Están los 14: `EmptyQwenImageLayeredLatentImage`, `EmptyFlux2LatentImage` (klein por el cargador común), `TextEncodeQwenImageEditPlus`, `LoadBackgroundRemovalModel` + `RemoveBackground` (BiRefNet, nodo propio de ComfyUI), `ZImageFunControlnet`, `InpaintModelConditioning`, `ControlNetApplyAdvanced`, `LoraLoaderModelOnly`, `IPAdapterAdvanced`, `ImageStitch`… **No hace falta actualizar ComfyUI** |
| Ida y vuelta por WebSocket (5 veces) | 0,32 s / 0,06 s la primera, después **0,02 s** |
| Ida y vuelta por *polling* de `/history` | **1,01 s** siempre (el intervalo de 1 s) |
| Subir un PNG de 1280 × 720 / bajar el resultado | 0,004 s / 0,001 s |
| Error de validación (imagen que no existe) | Llega como «ComfyUI no aceptó el pedido», con el detalle del nodo (`node_errors`) |
| Error al ejecutar (`ImageToMask` alfa sobre RGB) | Llega por el WebSocket (`execution_error`) como «ComfyUI falló al hacer la imagen» + `ImageToMask: index 3 is out of bounds…` |
| ComfyUI apagado | «La compu que hace las imágenes está apagada» |
| WebSocket que no conecta | Cae a *polling* y termina bien (1 imagen) |
| WebSocket cortado a mitad de camino | Cae a *polling* con el mismo pedido (no lo encola dos veces) y termina bien |
| Dos pedidos a la vez, sin lock | Se intercalan (ComfyUI los encola, pero el sitio no podría mirar la VRAM entre pasos) |
| Dos pedidos a la vez, con `asyncio.Lock` | **En serie**: B empieza cuando termina A (T3 de la spec funciona) |

### Con un modelo de verdad (Z-Image Turbo fp8 AIO, 1344 × 768, 5 pasos, `e0_vram.py`)

| | Segundos | VRAM pico (toda la placa) |
|---|---|---|
| En frío (carga el modelo) | 45,2 | **10 937 MB** |
| En caliente | 24,9 | 9 034 MB |
| En caliente | 24,9 | 9 029 MB |

- VRAM libre: 10 735 MB al empezar → 3 343 MB con el modelo cargado → **10 735 MB después de `/free`** (devuelve todo, al instante).
- La imagen de prueba (un pueblo con niebla y un farol, en blanco y negro) ya se parece al arte del canal (§1.7) sin ajustes.

## Lo que se ve

1. **La conexión desde el contenedor anda igual que desde el host.** `host.docker.internal` alcanza; no hace falta abrir nada más.
2. **WebSocket como camino principal**, *polling* como respaldo: el WebSocket no suma tiempo; el *polling* suma hasta 1 s por paso (aceptable como respaldo; se puede bajar a 0,5 s).
3. **Los errores llegan legibles** en los tres casos (validación, ejecución, apagado), con el detalle técnico aparte para el log.
4. **El lock es necesario** y funciona: sin él, dos pedidos se intercalan.
5. **La VRAM está justa:** Z-Image en frío llega a ~10,9 GB de 11,9 GB. Con audiogen generando a la vez no va a entrar. El turno de la GPU (T2.5) y `/free` entre pasos no son opcionales; se miden en E9 con audiogen activo.
6. **Candidato nuevo para E1/E3:** `ZImageFunControlnet` (ControlNet de Z-Image) viene en ComfyUI. Podría pasar de boceto a imagen con el modelo que ya rinde en esta placa. Hay que encontrar el modelo y verificar su licencia antes de bajarlo.

## Propuesta

**Sí**: el camino de la spec queda confirmado. Para S2 (T2.2):
- `httpx` + `websockets`, sin dependencias nuevas;
- el *polling* como respaldo con intervalo de 0,5–1 s;
- `/free` después de cada paso con un modelo grande;
- el lock de proceso.

Agregar `websockets` como dependencia explícita en `pyproject.toml` (hoy es transitiva) se pregunta en S2.
