# Miniaturas (Spec-790)

Todo lo que decide cómo se ven las miniaturas vive acá, fuera del código (D17):

- `arte.yaml`: las 4 plantillas, los tonos por lugar y los números de cada paso. Lo valida `src/application/services/miniatura/arte.py` al arrancar.
- `prompts/<paso>.md`: un prompt por paso. `{descripcion}` lo llena el arnés con lo que separó la IA (en inglés y en positivo: con cfg 1 el «no» trae lo que se niega, D27).
- `workflows/<receta>/`: los grafos de ComfyUI, uno por tarea (D15).

## Cambiar el arte

1. Tocar `arte.yaml` o el prompt del paso.
2. `uv run pytest tests/unit/test_miniatura_imagen.py tests/unit/application/miniatura` (con `SNAPSHOT_UPDATE=1` si cambió un prompt a propósito).
3. Armar una tanda en dev. El personaje y el escenario se rehacen solos si cambió su prompt o su número (van en el hash de la pieza); si solo cambió el color o el tono, se recolorea sin GPU.

## Sumar o reexportar un workflow

Cada receta es una carpeta con:

- `workflow.api.json`: el grafo exportado de ComfyUI con «Export (API)».
- `params.yaml`: lo único que el código cambia del grafo, `nombre: { node, input }`. Las imágenes de entrada son `LoadImage` (el cliente las sube y pone el nombre); `prefijo` es el `filename_prefix` del `SaveImage`.
- `README.md`: de qué spike sale, modelos, parámetros y cuánto tarda en la RTX 3060.

Para reexportar: abrir `workflow.api.json` en ComfyUI, cambiar, «Export (API)» y verificar que los nodos de `params.yaml` sigan existiendo. Lo cuida `tests/unit/test_comfy_client.py::test_los_workflows_tienen_los_nodos_de_sus_params`. Una receta nueva se usa con `ComfyClient.correr("<receta>", valores, entradas, destino)` y se agrega a `tests/support/fake_comfy.py` si devuelve otra cosa que la imagen de entrada.

| Receta | Qué hace | Modelo |
|---|---|---|
| `boceto_a_imagen` | boceto → personaje o escenario; también el fundido sobre el recorte | Qwen-Image-Edit 2511 + Lightning |
| `foto_img2img` | el personaje de Qwen → foto con flash (0,50) | Z-Image Turbo |
| `foto_controlnet` | el escenario de Qwen → foto de noche (0,75, con el boceto de guía a 0,6) | Z-Image Turbo + Fun ControlNet Union |
| `recortar` | la figura o lo importante del escenario → máscara | BiRefNet |
